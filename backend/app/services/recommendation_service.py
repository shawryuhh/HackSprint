"""Recommendation approval — the human approval gate.

Approving a recommendation is the only way a recommendation-driven dispatch
happens: this module owns its own atomic transaction (lock incident -> lock
the pending recommendation -> lock resources, in that fixed order, same
pattern as assignment_service) rather than routing through the public
POST /assignments endpoint, so `approved_by`/`decision_source` can never be
spoofed from a request body — they're set here, server-side, from the caller
identity `require_coordinator` already authenticated.

Locking a single recommendation row is enough to serialize concurrent
approval attempts for the same incident: the partial unique index
(uq_recommendation_pending_incident) guarantees at most one PENDING row
exists, so whichever request's SELECT ... FOR UPDATE gets there first wins;
the second blocks, then re-reads a row that's no longer PENDING and fails
with StaleRecommendationError instead of double-dispatching.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ResourceUnavailableError,
    StaleRecommendationError,
)
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus, IncidentStatus, OperationalPhase, RecommendationState, ResourceStatus
from app.models.recommendation import Recommendation
from app.schemas.recommendation import RecommendationApprove, RecommendationResponse
from app.services import id_generator
from app.services.action_log_service import record_action
from app.services.assignment_service import TERMINAL_INCIDENT_STATUSES, lock_incident, lock_resources
from app.services.state_machine import ALLOWED_RESOURCE_TRANSITIONS, assert_transition_allowed


def to_response(recommendation: Recommendation) -> RecommendationResponse:
    return RecommendationResponse.model_validate(recommendation)


def get_current_recommendation(db: Session, incident_id: str) -> RecommendationResponse:
    recommendation = (
        db.execute(
            select(Recommendation)
            .where(Recommendation.incident_id == incident_id)
            .order_by(Recommendation.version.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if recommendation is None:
        raise NotFoundError(f"No recommendation exists for incident '{incident_id}'.")
    return to_response(recommendation)


def _lock_pending_recommendation(db: Session, incident_id: str) -> Recommendation:
    return (
        db.execute(
            select(Recommendation)
            .where(
                Recommendation.incident_id == incident_id,
                Recommendation.state == RecommendationState.PENDING,
            )
            .with_for_update()
        )
        .scalars()
        .first()
    )


def approve_recommendation(
    db: Session, incident_id: str, payload: RecommendationApprove, approved_by: str
) -> RecommendationResponse:
    try:
        incident = lock_incident(db, incident_id)
        if incident.status in TERMINAL_INCIDENT_STATUSES:
            raise ConflictError(
                f"Incident '{incident.id}' is {incident.status.value}; cannot approve a recommendation."
            )

        recommendation = _lock_pending_recommendation(db, incident_id)
        if recommendation is None:
            raise StaleRecommendationError(
                f"Incident '{incident_id}' has no pending recommendation to approve."
            )
        if recommendation.version != payload.version:
            raise StaleRecommendationError(
                f"Recommendation version {payload.version} is stale; the current pending "
                f"version is {recommendation.version}."
            )

        resources = lock_resources(db, recommendation.recommended_resources)
        unavailable = [r.id for r in resources if r.status != ResourceStatus.AVAILABLE]
        if unavailable:
            raise ResourceUnavailableError(
                f"Resource(s) not AVAILABLE: {', '.join(unavailable)}."
            )

        recommendation.state = RecommendationState.APPROVED
        recommendation.decided_by = approved_by
        recommendation.decided_at = func.now()

        if incident.status == IncidentStatus.UNASSIGNED:
            incident.status = IncidentStatus.ASSIGNED
        incident.operational_phase = OperationalPhase.DISPATCHED

        record_action(
            db,
            source="coordinator",
            action="approved",
            incident_id=incident.id,
            metadata={"recommendation_id": recommendation.id, "version": recommendation.version},
        )

        for resource in resources:
            assert_transition_allowed(
                "Resource", resource.status, ResourceStatus.DISPATCHED, ALLOWED_RESOURCE_TRANSITIONS
            )
            resource.status = ResourceStatus.DISPATCHED

            assignment = Assignment(
                id=id_generator.next_assignment_id(db),
                incident_id=incident.id,
                resource_id=resource.id,
                status=AssignmentStatus.ASSIGNED,
                decision_source="coordinator_approval",
                approved_by=approved_by,
                recommendation_id=recommendation.id,
            )
            db.add(assignment)
            db.flush()

            record_action(
                db,
                source="coordinator",
                action="resource_dispatched",
                incident_id=incident.id,
                resource_id=resource.id,
                assignment_id=assignment.id,
                metadata={"recommendation_id": recommendation.id, "approved_by": approved_by},
            )

        db.commit()
        db.refresh(recommendation)
        return to_response(recommendation)
    except IntegrityError:
        # Backstop, same as assignment_service.create_assignment: a race that
        # got past the row locks above is caught by the partial unique index
        # and surfaced as a 409 instead of a raw 500.
        db.rollback()
        raise ConflictError(
            "One or more resources were assigned to another incident concurrently. Retry."
        )
    except Exception:
        db.rollback()
        raise
