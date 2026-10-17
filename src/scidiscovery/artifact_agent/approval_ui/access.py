"""Legacy import surface for the shared instance browser access primitives."""
from ...browser_access import (
    BrowserAccess,
    BrowserAccessDenied,
    BrowserAccessService,
    access_cookie,
    cookie_name,
    management_cookie,
    management_token,
)

__all__ = [
    "BrowserAccess", "BrowserAccessDenied", "BrowserAccessService",
    "access_cookie", "cookie_name", "management_cookie", "management_token",
]
