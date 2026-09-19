from pydantic import BaseModel

from app.schemas.assignment import AssignmentResponse
from app.schemas.incident import IncidentResponse


class ReplanningResponse(BaseModel):
    incident: IncidentResponse
    superseded_assignment: AssignmentResponse
    new_assignments: list[AssignmentResponse]
