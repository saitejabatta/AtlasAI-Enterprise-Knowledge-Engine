from contextvars import ContextVar, Token


_workspace_id: ContextVar[str | None] = ContextVar(
    "atlas_workspace_id",
    default=None,
)


def get_workspace_id() -> str | None:
    return _workspace_id.get()


def set_workspace_id(workspace_id: str) -> Token:
    return _workspace_id.set(workspace_id)


def reset_workspace_id(token: Token) -> None:
    _workspace_id.reset(token)
