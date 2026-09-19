"""Fixed state-machine enums.

Unlike `type` fields (see app.core.domain_values), these represent genuine
finite state machines with explicitly allowed transitions enforced in the
service layer (see app/services/*_service.py). They are intentionally rigid.
"""

from enum import Enum


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class ResourceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DISPATCHED = "DISPATCHED"
    ACTIVE = "ACTIVE"
    UNAVAILABLE = "UNAVAILABLE"


class AssignmentStatus(str, Enum):
    ASSIGNED = "ASSIGNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"
