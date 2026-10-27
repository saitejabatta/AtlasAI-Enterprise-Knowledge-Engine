import os

from starlette.requests import Request
from starlette.responses import JSONResponse

from auth import SESSION_COOKIE_NAME, get_session_user
from workspace_context import reset_workspace_id, set_workspace_id


PUBLIC_PATHS = {
    "/",
    "/health",
    "/auth/register",
    "/auth/login",
}
DEFAULT_ORIGINS = {
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
}


def origin_is_allowed(origin: str) -> bool:
    configured = os.getenv("ATLAS_ALLOWED_ORIGINS")
    if configured is None:
        return origin in DEFAULT_ORIGINS
    origins = {
        item.strip()
        for item in configured.split(",")
        if item.strip()
    }
    return "*" in origins or origin in origins


class WorkspaceAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()
        request = Request(scope)
        origin = request.headers.get("origin")
        if (
            method in {"POST", "PUT", "PATCH", "DELETE"}
            and origin
            and not origin_is_allowed(origin)
        ):
            response = JSONResponse(
                {"success": False, "error": "Request origin is not allowed"},
                status_code=403,
            )
            await response(scope, receive, send)
            return

        if method == "OPTIONS" or path in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        user = get_session_user(
            request.cookies.get(SESSION_COOKIE_NAME)
        )
        if not user:
            response = JSONResponse(
                {
                    "success": False,
                    "error": "Authentication required",
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        scope.setdefault("state", {})["user"] = user
        token = set_workspace_id(user["workspace_id"])
        try:
            await self.app(scope, receive, send)
        finally:
            reset_workspace_id(token)
