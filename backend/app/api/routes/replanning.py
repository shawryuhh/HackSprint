from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.common_responses import CONFLICT, NOT_FOUND, VALIDATION_FAILED, responses
from app.api.deps import get_db, verify_api_key
from app.schemas.assignment import ReplanningRequest
from app.schemas.replanning import ReplanningResponse
from app.services import replanning_service

router = APIRouter(tags=["replanning"], dependencies=[Depends(verify_api_key)])


@router.post(
    "/replanning",
    response_model=ReplanningResponse,
    status_code=201,
    summary="Replan: swap a resource on a live assignment for one or more replacements",
    description="Used when a dispatched resource can no longer fulfill its assignment (e.g. a "
    "road block) and the AI/human decision is to reassign. Atomically supersedes the old "
    "assignment (kept, never deleted), frees the old resource, and creates new assignment(s) "
    "for the replacement resource(s).",
    responses=responses(NOT_FOUND, CONFLICT, VALIDATION_FAILED),
)
def replan(payload: ReplanningRequest, db: Session = Depends(get_db)) -> ReplanningResponse:
    return replanning_service.replan(db, payload)
