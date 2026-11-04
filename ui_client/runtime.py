"""Process-local owner isolation; authenticated middleware establishes Execution.

There is deliberately no configured-owner/default-user fallback here. This cache
is not a shared replica store or a durable job scheduler.
"""
from collections.abc import MutableMapping
from contextvars import ContextVar
from dataclasses import dataclass
import copy

from starlette.responses import JSONResponse
from common.security import SecurityError, execution
from .store import StoreConflict, tenant_id


def runtime_owner():
    context = execution.get()
    if context is None:
        raise SecurityError("Verified owner context is required for runtime state")
    try:
        tenant_id(context.owner)
    except ValueError as exc:
        raise SecurityError("Invalid runtime owner") from exc
    return context.owner.strip().lower()


@dataclass
class RuntimeView:
    owner: str
    state: dict
    revision: int
    cursor: int = 0
    baseline: dict | None = None
    conflicted: bool = False


class OwnerRuntime(MutableMapping):
    """Mapping facade resolving the verified owner on every access."""
    def __init__(self, factory):
        self._factory = factory
        self._owners = {}
        self._revisions = {}
        self._view = ContextVar("pipeline_view", default=None)

    def _state(self):
        owner = runtime_owner()
        view = self.current_view()
        if view is not None:
            return view.state
        if owner not in self._owners:
            self._owners[owner] = self._factory()
        return self._owners[owner]

    def current_view(self):
        view = self._view.get()
        if view is not None and view.owner != runtime_owner():
            raise SecurityError("Runtime view owner mismatch")
        return view

    def bind(self, revision):
        return self._view.set(RuntimeView(runtime_owner(), self._factory(), revision))

    def unbind(self, token):
        self._view.reset(token)

    def cache_current(self):
        view = self.current_view()
        if (view is not None and view.baseline is not None and not view.conflicted
                and view.revision >= self._revisions.get(view.owner, 0)):
            self._owners[view.owner] = copy.deepcopy(view.state)
            self._revisions[view.owner] = view.revision

    def revision(self):
        view = self.current_view()
        return view.revision if view is not None else self._revisions.get(runtime_owner(), 0)

    def clear_all(self):
        """Application lifecycle only; request resets use clear()."""
        self._owners.clear()
        self._revisions.clear()

    def __getitem__(self, key):
        return self._state()[key]

    def __setitem__(self, key, value):
        self._state()[key] = value

    def __delitem__(self, key):
        del self._state()[key]

    def __iter__(self):
        return iter(self._state())

    def __len__(self):
        return len(self._state())


class PipelineRuntimeMiddleware:
    """Bind an authoritative independent view beneath authenticated middleware."""
    def __init__(self, app, scope_factory, flush):
        self.app, self.scope_factory, self.flush = app, scope_factory, flush

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"} or execution.get() is None:
            return await self.app(scope, receive, send)
        started = False
        async def committed_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                if message["status"] < 400:
                    await self.flush()
                started = True
            await send(message)
        try:
            async with self.scope_factory():
                await self.app(scope, receive, committed_send)
        except StoreConflict:
            if started:
                raise
            await JSONResponse({"error": "Pipeline changed; reload before retrying", "code": "pipeline_conflict"}, 409)(scope, receive, send)
