"""Domain exceptions raised by the service layer.

Route handlers never construct HTTPException directly for business errors —
they let these propagate and a single set of handlers (registered in main.py)
translates them into consistent JSON error responses.
"""


class DomainError(Exception):
    """Base class for all business-rule errors raised by the service layer."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    """Raised when a referenced entity does not exist."""


class ConflictError(DomainError):
    """Raised when an operation cannot proceed due to the current state of the data
    (e.g. a resource is already assigned, or a state transition is disallowed)."""


class ValidationFailedError(DomainError):
    """Raised for business-rule validation failures that aren't caught by Pydantic
    (e.g. a well-formed but semantically invalid request)."""
