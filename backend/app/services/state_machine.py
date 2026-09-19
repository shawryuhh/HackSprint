"""Explicit state transition tables for incidents, resources and assignments.

A transition is only allowed if it appears in the relevant map below. This is
the single place these rules are defined — services call
`assert_transition_allowed` instead of hand-rolling if/else chains, so the
rules can't drift out of sync between endpoints.
"""

from app.core.exceptions import ConflictError
from app.models.enums import AssignmentStatus, IncidentStatus, ResourceStatus

ALLOWED_RESOURCE_TRANSITIONS: dict[ResourceStatus, set[ResourceStatus]] = {
    ResourceStatus.AVAILABLE: {ResourceStatus.DISPATCHED, ResourceStatus.UNAVAILABLE},
    ResourceStatus.DISPATCHED: {
        ResourceStatus.ACTIVE,
        ResourceStatus.AVAILABLE,
        ResourceStatus.UNAVAILABLE,
    },
    ResourceStatus.ACTIVE: {ResourceStatus.AVAILABLE, ResourceStatus.UNAVAILABLE},
    ResourceStatus.UNAVAILABLE: {ResourceStatus.AVAILABLE},
}

ALLOWED_INCIDENT_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.UNASSIGNED: {IncidentStatus.ASSIGNED, IncidentStatus.CANCELLED},
    IncidentStatus.ASSIGNED: {
        IncidentStatus.ACTIVE,
        IncidentStatus.UNASSIGNED,
        IncidentStatus.CANCELLED,
    },
    IncidentStatus.ACTIVE: {IncidentStatus.RESOLVED, IncidentStatus.CANCELLED},
    IncidentStatus.RESOLVED: set(),
    IncidentStatus.CANCELLED: set(),
}

ALLOWED_ASSIGNMENT_TRANSITIONS: dict[AssignmentStatus, set[AssignmentStatus]] = {
    AssignmentStatus.ASSIGNED: {
        AssignmentStatus.ACTIVE,
        AssignmentStatus.CANCELLED,
        AssignmentStatus.SUPERSEDED,
    },
    AssignmentStatus.ACTIVE: {
        AssignmentStatus.COMPLETED,
        AssignmentStatus.CANCELLED,
        AssignmentStatus.SUPERSEDED,
    },
    AssignmentStatus.COMPLETED: set(),
    AssignmentStatus.CANCELLED: set(),
    AssignmentStatus.SUPERSEDED: set(),
}


def assert_transition_allowed(
    entity_name: str,
    current: object,
    target: object,
    allowed_map: dict,
) -> None:
    if current == target:
        raise ConflictError(f"{entity_name} is already in status {current}.")
    allowed = allowed_map.get(current, set())
    if target not in allowed:
        raise ConflictError(
            f"Cannot transition {entity_name} from {current} to {target}."
        )
