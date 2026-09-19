"""Replanning: swap a resource out of a live assignment for one or more
replacements, atomically. This is the AMB-02-hits-a-roadblock-so-reassign-to-
AMB-05 path — the backend never decides *that* a replan is needed or *which*
resource replaces the old one; it only enforces that the swap itself is safe
and fully auditable once the AI/human decision arrives.

Same locking discipline as assignment_service.create_assignment, extended to
also lock and release the resource being replaced:

1. Lock the incident.
2. Lock the old assignment — by id if given, else the current live
   assignment for incident_id + old_resource_id.
3. Re-validate the old assignment is still live *after* the lock is held.
   This is what stops two concurrent replans of the same assignment from
   both succeeding: the second one blocks on the row lock, then sees
   SUPERSEDED once it's unblocked and fails cleanly instead of double-
   superseding it.
4. Lock the old resource and all replacement resources together, in a single
   sorted-by-id SELECT ... FOR UPDATE (reusing
   assignment_service.lock_resources), so this can never deadlock against a
   concurrent create_assignment/replan touching an overlapping resource set.
5. Validate replacement resources are AVAILABLE — before mutating anything,
   so an unavailable replacement leaves the old assignment untouched.
6. Supersede the old assignment (never deleted, never rewritten again after
   this), release the old resource, create the new assignment(s), dispatch
   the new resource(s).
7. Log the whole thing to action_logs with enough metadata (old assignment
   id, replaced-by resource ids) to reconstruct the full history later.

All of it commits together, or none of it does.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus, ResourceStatus
from app.schemas.assignment import ReplanningRequest
from app.schemas.replanning import ReplanningResponse
from app.services import assignment_service, id_generator
from app.services.action_log_service import record_action
from app.services.assignment_service import LIVE_ASSIGNMENT_STATUSES, TERMINAL_INCIDENT_STATUSES
from app.services.incident_service import to_response as incident_to_response
from app.services.state_machine import ALLOWED_RESOURCE_TRANSITIONS, assert_transition_allowed


def _lock_old_assignment(db: Session, payload: ReplanningRequest) -> Assignment:
    if payload.old_assignment_id is not None:
        assignment = db.execute(
            select(Assignment)
            .where(Assignment.id == payload.old_assignment_id)
            .with_for_update()
        ).scalar_one_or_none()
        if assignment is None:
            raise NotFoundError(f"Assignment '{payload.old_assignment_id}' not found.")
        if (
            assignment.incident_id != payload.incident_id
            or assignment.resource_id != payload.old_resource_id
        ):
            raise ValidationFailedError(
                "old_assignment_id does not match the given incident_id/old_resource_id."
            )
        return assignment

    # Deliberately not filtered to live statuses here: an already-terminal
    # assignment for this incident/resource pair must still be found so the
    # caller gets a clear "already COMPLETED/CANCELLED" 409 below, not a
    # misleading 404 that implies the pairing never existed at all.
    assignment = db.execute(
        select(Assignment)
        .where(
            Assignment.incident_id == payload.incident_id,
            Assignment.resource_id == payload.old_resource_id,
        )
        .order_by(Assignment.created_at.desc())
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if assignment is None:
        raise NotFoundError(
            f"No assignment found for incident '{payload.incident_id}' and "
            f"resource '{payload.old_resource_id}'."
        )
    return assignment


def replan(db: Session, payload: ReplanningRequest) -> ReplanningResponse:
    if payload.old_resource_id in payload.new_resource_ids:
        raise ValidationFailedError("old_resource_id cannot also appear in new_resource_ids.")

    try:
        incident = assignment_service.lock_incident(db, payload.incident_id)
        if incident.status in TERMINAL_INCIDENT_STATUSES:
            raise ConflictError(
                f"Incident '{incident.id}' is {incident.status.value}; cannot replan."
            )

        old_assignment = _lock_old_assignment(db, payload)
        # Re-checked after the lock is held: if a concurrent replan/complete/
        # cancel already moved this assignment out of a live state, this call
        # loses the race cleanly instead of superseding it a second time.
        if old_assignment.status not in LIVE_ASSIGNMENT_STATUSES:
            raise ConflictError(
                f"Assignment '{old_assignment.id}' is already "
                f"{old_assignment.status.value}; cannot replan."
            )

        resources_by_id = {
            resource.id: resource
            for resource in assignment_service.lock_resources(
                db, [payload.old_resource_id, *payload.new_resource_ids]
            )
        }
        old_resource = resources_by_id[payload.old_resource_id]
        new_resources = [resources_by_id[rid] for rid in payload.new_resource_ids]

        unavailable = [r.id for r in new_resources if r.status != ResourceStatus.AVAILABLE]
        if unavailable:
            raise ConflictError(f"Resource(s) not AVAILABLE: {', '.join(unavailable)}.")

        if payload.ai_recommendation is not None:
            record_action(
                db,
                source="ai",
                action="ai_recommendation_received",
                incident_id=incident.id,
                metadata=payload.ai_recommendation.model_dump(),
            )

        # Release the old resource and supersede its assignment. Never
        # deleted — SUPERSEDED is a terminal state, preserved for audit.
        assert_transition_allowed(
            "Resource", old_resource.status, ResourceStatus.AVAILABLE, ALLOWED_RESOURCE_TRANSITIONS
        )
        old_resource.status = ResourceStatus.AVAILABLE
        old_assignment.status = AssignmentStatus.SUPERSEDED
        db.flush()

        record_action(
            db,
            source=payload.decision_source,
            action="assignment_superseded",
            reason=payload.reason,
            incident_id=incident.id,
            resource_id=old_resource.id,
            assignment_id=old_assignment.id,
            metadata={"replaced_by_resources": payload.new_resource_ids},
        )

        # Dispatch the replacement(s).
        new_assignments: list[Assignment] = []
        for resource in new_resources:
            assert_transition_allowed(
                "Resource", resource.status, ResourceStatus.DISPATCHED, ALLOWED_RESOURCE_TRANSITIONS
            )
            resource.status = ResourceStatus.DISPATCHED

            new_assignment = Assignment(
                id=id_generator.next_assignment_id(db),
                incident_id=incident.id,
                resource_id=resource.id,
                status=AssignmentStatus.ASSIGNED,
                decision_source=payload.decision_source,
                approved_by=payload.approved_by,
            )
            db.add(new_assignment)
            db.flush()
            new_assignments.append(new_assignment)

            record_action(
                db,
                source=payload.decision_source,
                action="assignment_created",
                reason=payload.reason,
                incident_id=incident.id,
                resource_id=resource.id,
                assignment_id=new_assignment.id,
                metadata={
                    "replanned_from_assignment_id": old_assignment.id,
                    "approved_by": payload.approved_by,
                },
            )

        db.commit()
        db.refresh(incident)
        db.refresh(old_assignment)
        for new_assignment in new_assignments:
            db.refresh(new_assignment)

        return ReplanningResponse(
            incident=incident_to_response(db, incident),
            superseded_assignment=assignment_service.to_response(old_assignment),
            new_assignments=[assignment_service.to_response(a) for a in new_assignments],
        )
    except IntegrityError:
        # Backstop: the partial unique index caught a race that got past the
        # row locks above.
        db.rollback()
        raise ConflictError(
            "One or more replacement resources were assigned concurrently. Retry."
        )
    except Exception:
        db.rollback()
        raise
