"""Process-local owner isolation; authenticated middleware establishes Execution.

There is deliberately no configured-owner/default-user fallback here. This cache
is not a shared replica store or a durable job scheduler.
"""
from collections.abc import MutableMapping

from common.security import SecurityError, execution
from .store import tenant_id


def runtime_owner():
    context = execution.get()
    if context is None:
        raise SecurityError("Verified owner context is required for runtime state")
    try:
        tenant_id(context.owner)
    except ValueError as exc:
        raise SecurityError("Invalid runtime owner") from exc
    return context.owner.strip().lower()


class OwnerRuntime(MutableMapping):
    """Mapping facade resolving the verified owner on every access."""
    def __init__(self, factory):
        self._factory = factory
        self._owners = {}

    def _state(self):
        owner = runtime_owner()
        if owner not in self._owners:
            self._owners[owner] = self._factory()
        return self._owners[owner]

    def clear_all(self):
        """Application lifecycle only; request resets use clear()."""
        self._owners.clear()

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
