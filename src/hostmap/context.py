"""Active-host context propagation via a contextvar.

The active entry lives in a ``contextvars.ContextVar``, mirroring how Django
itself propagates the urlconf under ASGI (asgiref locals). No thread locals,
so concurrent ASGI requests on different hosts never leak host context
(BR-HOSTMAP-001, AC-HOSTMAP-016). Outside a request the contextvar is unset,
and readers fall back to the ``HOSTMAP_DEFAULT`` entry (BR-HOSTMAP-006).

Setting the active entry also calls Django's ``set_urlconf()`` so that stock
``reverse()`` (which resolves ``urlconf=None`` via ``get_urlconf()``) picks
the active host's URLconf natively. Same-host reversing is then byte-identical
to stock Django (BR-HOSTMAP-003) even under ``use_host()`` and out of a
request; the resolver seam only adds cross-host fallback on top.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

from django.urls import set_urlconf

if TYPE_CHECKING:
    from hostmap.map import ResolvedEntry

_active_entry: ContextVar[ResolvedEntry | None] = ContextVar("hostmap_active_entry", default=None)
# Remembers the urlconf in force before each ``set_active`` so ``reset_active``
# can restore it, mirroring the contextvar token dance. The default is None
# (no mutable default); the stack is copied on write, never mutated in place.
_urlconf_stack: ContextVar[tuple | None] = ContextVar("hostmap_urlconf_stack", default=None)


def set_active(entry: ResolvedEntry | None) -> object:
    """Set the active entry and sync Django's urlconf. Returns a reset token."""
    from django.urls import get_urlconf

    previous_urlconf = get_urlconf()
    stack = _urlconf_stack.get() or ()
    _urlconf_stack.set((*stack, previous_urlconf))

    token = _active_entry.set(entry)
    if entry is not None and not entry.is_redirect:
        set_urlconf(entry.urlconf)
    return token


def reset_active(token: object) -> None:
    """Restore the previous active entry and urlconf using the token."""
    _active_entry.reset(token)
    stack = _urlconf_stack.get()
    if stack:
        previous_urlconf = stack[-1]
        _urlconf_stack.set(stack[:-1])
        set_urlconf(previous_urlconf)


def get_active() -> ResolvedEntry | None:
    """Return the active entry, or the ``HOSTMAP_DEFAULT`` entry outside a request.

    Returns ``None`` only when no entry is active and no default is
    configured (an empty or misconfigured map).
    """
    entry = _active_entry.get()
    if entry is not None:
        return entry
    from hostmap.map import default_entry

    return default_entry()
