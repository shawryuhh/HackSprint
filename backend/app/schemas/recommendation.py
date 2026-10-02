from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RecommendationState


class RecommendationApprove(BaseModel):
    """Body for POST .../recommendation/approve.

    Deliberately just the version being approved — no `approved_by`. That
    identity is never taken from the request; it's derived server-side from
    the authenticated coordinator API key (D9). `extra="forbid"` means a
    client that tries to smuggle one in gets a 422, not silent ignoring.
    """

    version: int = Field(gt=0, description="The version of the currently pending plan being approved.")

    model_config = ConfigDict(extra="forbid")


class RecommendationResponse(BaseModel):
    """Matches frontend's `Recommendation` type (types/index.ts) field-for-field,
    plus internal bookkeeping fields (id, decided_by/at, timestamps) the
    contract doesn't define but doesn't forbid either — existing response
    schemas in this codebase (e.g. AssignmentResponse) take the same
    superset-of-the-documented-shape approach.
    """

    id: str
    # Frontend's Recommendation.incident, not incident_id — the ORM column is
    # incident_id, so this is the one place we alias rather than invent.
    incident: str = Field(validation_alias="incident_id")
    version: int
    state: RecommendationState
    recommended_resources: list[str]
    reason: str
    explanation: list[dict[str, Any]]
    confidence: float | None = None
    priority_score: int | None = None
    replacementFor: str | None = Field(default=None, validation_alias="replacement_for_resource_id")
    approval_required: bool = True
    decided_by: str | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
