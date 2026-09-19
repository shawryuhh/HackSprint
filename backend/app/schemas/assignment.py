from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AssignmentStatus
from app.schemas.ai import AIRecommendation


class AssignmentCreate(BaseModel):
    incident_id: str
    resource_ids: list[str] = Field(
        min_length=1,
        description="One or more resources to assign to the incident in a single atomic operation.",
    )
    decision_source: str = Field(
        description='Who/what decided this assignment, e.g. "ai", "human", "n8n".'
    )
    approved_by: str | None = Field(
        default=None, description="Identity of the human who approved this assignment, if any."
    )
    reason: str | None = None
    ai_recommendation: AIRecommendation | None = Field(
        default=None,
        description="Optional pass-through of the AI recommendation this assignment fulfills, for audit logging.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "INC-1042",
                "resource_ids": ["AMB-02", "RESCUE-01"],
                "decision_source": "ai",
                "approved_by": "dispatcher_1",
                "reason": "Medical emergency involving a vulnerable person",
            }
        }
    )


class AssignmentResponse(BaseModel):
    id: str
    incident_id: str
    resource_id: str
    status: AssignmentStatus
    assigned_at: datetime
    completed_at: datetime | None
    decision_source: str
    approved_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignmentStatusUpdate(BaseModel):
    status: AssignmentStatus
    reason: str | None = None


class ReplanningRequest(BaseModel):
    incident_id: str
    old_resource_id: str = Field(description="The resource being released, e.g. AMB-02.")
    old_assignment_id: str | None = Field(
        default=None,
        description="Explicit assignment to supersede. If omitted, the current live "
        "assignment for incident_id + old_resource_id is used.",
    )
    new_resource_ids: list[str] = Field(min_length=1)
    reason: str = Field(description='Why replanning was triggered, e.g. "road_blocked".')
    decision_source: str
    approved_by: str | None = None
    ai_recommendation: AIRecommendation | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "INC-1042",
                "old_resource_id": "AMB-02",
                "new_resource_ids": ["AMB-05"],
                "reason": "road_blocked",
                "decision_source": "ai",
                "approved_by": "dispatcher_1",
            }
        }
    )
