from app.core.exceptions import BaseServiceError


class UserHasActiveCallError(BaseServiceError):
    """Raised when attempting to deactivate a user with an IN_PROGRESS task."""
