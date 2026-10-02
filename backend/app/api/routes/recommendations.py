from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.common_responses import CONFLICT, NOT_FOUND, responses
from app.api.deps import get_db, require_coordinator, verify_api_key
from app.schemas.recommendation import RecommendationApprove, RecommendationResponse
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
    "/{incident_id}/recommendation/approve",
    response_model=RecommendationResponse,
    summary="Approve the current pending recommendation",
    description="The human approval gate: atomically approves the pending recommendation, "
    "dispatches its recommended resources (creating assignments that reference it), and "
    "updates incident/resource state. `approved_by` is always derived from the authenticated "
    "coordinator API key, never from the request body. Only PENDING recommendations at the "
    "exact requested version can be approved.",
    responses=responses(NOT_FOUND, CONFLICT),
)
def approve_recommendation(
    incident_id: str,
    payload: RecommendationApprove,
    db: Session = Depends(get_db),
    approved_by: str = Depends(require_coordinator),
) -> RecommendationResponse:
    return recommendation_service.approve_recommendation(db, incident_id, payload, approved_by)
