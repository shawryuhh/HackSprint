from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.common_responses import CONFLICT, NOT_FOUND, VALIDATION_FAILED, responses
from app.api.deps import get_db, require_coordinator, verify_any_api_key, verify_api_key
from app.schemas.recommendation import (
    RecommendationApprove,
    RecommendationCreate,
    RecommendationProposeReplacement,
    RecommendationResponse,
)
from app.services import recommendation_service

router = APIRouter(prefix="/integration/v1/incidents", tags=["recommendations"])


@router.get(
    "/{incident_id}/recommendation",
    response_model=RecommendationResponse,
    summary="Get the current recommendation for an incident",
    description="Returns the highest-versioned recommendation for the incident, regardless "
    "of its state (pending/approved/rejected) — the current plan, decided or not.",
    responses=responses(NOT_FOUND),
    dependencies=[Depends(verify_api_key)],
)
def get_current_recommendation(incident_id: str, db: Session = Depends(get_db)) -> RecommendationResponse:
    return recommendation_service.get_current_recommendation(db, incident_id)


@router.post(
    "/{incident_id}/recommendation",
    response_model=RecommendationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit the initial recommendation for an incident",
    description="AI/n8n intake for the first plan (version 1). Stores it as PENDING and moves "
    "the incident to `awaiting_approval`; nothing is reserved or dispatched until a coordinator "
    "approves it. Resending the same `analysis_revision` with the same plan replays the existing "
    "recommendation (200) instead of creating a second one.",
    responses=responses(NOT_FOUND, CONFLICT, VALIDATION_FAILED),
    dependencies=[Depends(verify_any_api_key)],
)
def create_recommendation(
    incident_id: str,
    payload: RecommendationCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    recommendation, created = recommendation_service.create_recommendation(db, incident_id, payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return recommendation


@router.post(
    "/{incident_id}/recommendation/replacement",
    response_model=RecommendationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Propose a replacement plan for a blocked incident",
    description="Stores a new PENDING version replacing `replacement_for` and moves the incident "
    "to `awaiting_replacement`. `recommended_resources` is the complete new plan (continuing "
    "responders included). `base_version` must be the currently approved version. Nothing is "
    "released or dispatched until a coordinator approves it. Idempotent on `analysis_revision` "
    "like the initial submission.",
    responses=responses(NOT_FOUND, CONFLICT, VALIDATION_FAILED),
    dependencies=[Depends(verify_any_api_key)],
)
def propose_replacement(
    incident_id: str,
    payload: RecommendationProposeReplacement,
    response: Response,
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    recommendation, created = recommendation_service.propose_replacement(db, incident_id, payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return recommendation


@router.post(
    "/{incident_id}/recommendation/approve",
    response_model=RecommendationResponse,
    summary="Approve the current pending recommendation",
    description="The human approval gate: atomically approves the pending recommendation, "
    "dispatches its recommended resources (creating assignments that reference it), and "
    "updates incident/resource state. `approved_by` is always derived from the authenticated "
    "coordinator API key, never from the request body. Only PENDING recommendations at the "
    "exact requested version can be approved. For a replacement plan, responders no longer in "
    "the plan are released (assignment SUPERSEDED), continuing ones are left untouched, and "
    "newcomers are dispatched — all in one transaction.",
    responses=responses(NOT_FOUND, CONFLICT),
)
def approve_recommendation(
    incident_id: str,
    payload: RecommendationApprove,
    db: Session = Depends(get_db),
    approved_by: str = Depends(require_coordinator),
) -> RecommendationResponse:
    return recommendation_service.approve_recommendation(db, incident_id, payload, approved_by)
