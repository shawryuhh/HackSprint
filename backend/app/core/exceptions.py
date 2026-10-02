"""Domain exceptions raised by the service layer.

Route handlers never construct HTTPException directly for business errors —
they let these propagate and a single set of handlers (registered in main.py)
translates them into consistent JSON error responses.
"""


class DomainError(Exception):
    """Base class for all business-rule errors raised by the service layer.

    `code` is an optional, stable machine-readable string (e.g. "STALE_PLAN")
    for callers that need to branch on the failure reason instead of parsing
    `message`. Existing raises that don't pass one keep getting `code: null`
    in the response — this is purely additive.
    """

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(DomainError):
    """Raised when a referenced entity does not exist."""


class ConflictError(DomainError):
    """Raised when an operation cannot proceed due to the current state of the data
    (e.g. a resource is already assigned, or a state transition is disallowed)."""


class ValidationFailedError(DomainError):
    """Raised for business-rule validation failures that aren't caught by Pydantic
    (e.g. a well-formed but semantically invalid request)."""


class StaleRecommendationError(ConflictError):
    """The recommendation being approved is no longer the current pending one —
    already decided, or a newer version exists (code=STALE_PLAN)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="STALE_PLAN")


class ResourceUnavailableError(ConflictError):
    """One or more resources in the recommendation are no longer AVAILABLE
    (code=RESOURCE_UNAVAILABLE)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="RESOURCE_UNAVAILABLE")


class ApprovalRequiredError(ConflictError):
    """Raised by POST /assignments when the requested dispatch isn't backed
    by a valid, current, APPROVED recommendation covering the requested
    resource(s) — the direct-dispatch bypass this guards against
    (code=APPROVAL_REQUIRED)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="APPROVAL_REQUIRED")
