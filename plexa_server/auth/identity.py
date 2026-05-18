from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


AuthType = Literal["anonymous", "dev_header", "bearer_jwt"]


@dataclass(slots=True)
class UserIdentity:
    """Canonical request identity resolved by auth middleware.

    Attributes:
        user_id: Authenticated user identifier when available.
        roles: Normalized role set for authorization checks.
        claims: Provider-specific metadata preserved for downstream use.
        auth_type: Identity source used to construct this principal.
    """

    user_id: str | None = None
    roles: set[str] = field(default_factory=set)
    claims: dict[str, Any] = field(default_factory=dict)
    auth_type: AuthType = "anonymous"

    @property
    def is_authenticated(self) -> bool:
        """Return whether the request carries a user identity."""
        return self.user_id is not None

    @property
    def is_admin(self) -> bool:
        """Return whether the request carries administrative privileges."""
        return "admin" in self.roles

    @property
    def is_anonymous(self) -> bool:
        """Return whether no authenticated identity was resolved."""
        return not self.is_authenticated and not self.is_admin
