"""The single host-aware resolution code path and the explicit API.

Both the patched stock ``reverse()`` (via ``resolvers.py``) and the explicit
API (``hostmap.urls.reverse`` / ``build_absolute_uri``) delegate to the same
``_resolve()`` function. There are never two implementations of host-aware
resolution to keep in lockstep (03-services.md section 3, watch flag 2):
with ``HOSTMAP_PATCH_REVERSE = False`` the explicit API calls this logic
directly.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from django.urls import NoReverseMatch
from django.urls import reverse as django_reverse
from django.urls.base import get_script_prefix

from hostmap import context
from hostmap import map as hostmap_map
from hostmap.conf import hostmap_settings

logger = logging.getLogger("hostmap.reverse")


def _entry_order():
    """Cross-host resolution order (BR-HOSTMAP-005).

    Active host, then the default entry, then remaining entries in
    declaration order. Duplicates removed while preserving first sight.
    Wildcard entries never participate in cross-host reversing
    (BR-HOSTMAP-009); they are reachable only via ``use_host(host=...)``.
    """
    entries = hostmap_map.resolved_entries()
    ordered = []
    seen = set()

    def _add(entry):
        if entry is None or entry.label in seen:
            return
        if entry.is_redirect or entry.wildcard:
            return
        seen.add(entry.label)
        ordered.append(entry)

    _add(context.get_active())
    _add(hostmap_map.default_entry())
    for entry in entries.values():
        _add(entry)
    return ordered


def _absolute_url(entry, path: str) -> str:
    """Compose ``scheme://host[:port]`` + ``path`` for a cross-host entry (BR-HOSTMAP-004).

    ``path`` already includes the script prefix (Django's ``reverse`` prepends
    it), so it is used verbatim; this composes the authority only.
    """
    host = entry.host
    port = hostmap_settings.PORT
    if port:
        host = f"{host}:{port}"
    return f"{hostmap_settings.SCHEME}://{host}{path}"


def _resolve(name, args=None, kwargs=None, *, force_host_entry=None) -> str:
    """Host-aware reverse: the single resolution code path.

    Reverses ``name`` against the active host first. On ``NoReverseMatch`` it
    walks the other entries in BR-HOSTMAP-005 order and returns an absolute
    URL for the first host that resolves the name. Raises ``NoReverseMatch``
    naming the searched hosts if nothing resolves.

    ``force_host_entry`` pins resolution to one entry (used by ``use_host``
    and ``build_absolute_uri(host=...)``); the result is always absolute.
    """
    if force_host_entry is not None:
        path = django_reverse(name, urlconf=force_host_entry.urlconf, args=args, kwargs=kwargs)
        return _absolute_url(force_host_entry, path)

    order = _entry_order()
    active = order[0] if order else None

    # Try the active host first. A match here stays path-relative
    # (BR-HOSTMAP-003, byte-identical to stock Django).
    if active is not None:
        try:
            return django_reverse(name, urlconf=active.urlconf, args=args, kwargs=kwargs)
        except NoReverseMatch:
            pass

    # Cross-host fallback: first other entry that resolves wins.
    for entry in order[1:]:
        try:
            path = django_reverse(name, urlconf=entry.urlconf, args=args, kwargs=kwargs)
        except NoReverseMatch:
            continue
        logger.debug("hostmap cross-host reverse: %r -> host %s (%s)", name, entry.host, entry.label)
        return _absolute_url(entry, path)

    searched = ", ".join(e.host for e in order) or "(no hostmap entries)"
    raise NoReverseMatch(f"Reverse for '{name}' not found on any hostmap host. Searched: {searched}.")


# --- Explicit API (03-services.md section 3) -------------------------------


def reverse(name, args=None, kwargs=None) -> str:
    """Host-aware reverse with the same semantics as the patched stock reverse."""
    return _resolve(name, args=args, kwargs=kwargs)


def build_absolute_uri(name_or_path, args=None, kwargs=None, host=None) -> str:
    """Return an absolute URL regardless of the active host.

    ``name_or_path`` is either a URL name (reversed with ``args``/``kwargs``)
    or a ready-made path (starting with ``/``). ``host`` optionally pins the
    entry by label or by literal host (for wildcard entries).
    """
    entry = _host_to_entry(host) if host is not None else context.get_active()

    if isinstance(name_or_path, str) and name_or_path.startswith("/"):
        if entry is None:
            raise NoReverseMatch("build_absolute_uri: no active or specified host to build an absolute URL against.")
        return _absolute_url(entry, name_or_path)

    if host is not None:
        return _resolve(name_or_path, args=args, kwargs=kwargs, force_host_entry=entry)

    # No pinned host: reverse host-aware, then force absolute against the
    # active host when the result is still a same-host path.
    result = _resolve(name_or_path, args=args, kwargs=kwargs)
    if result.startswith("/") and entry is not None:
        return _absolute_url(entry, result)
    return result


@contextmanager
def use_host(label=None, host=None):
    """Treat the given entry (or explicit host) as active for reversing.

    The BR-HOSTMAP-006 override for emails, Celery tasks, API payloads and
    webhooks. Pass ``label`` for a named entry or ``host`` for a wildcard's
    concrete host (README open question 2).
    """
    entry = _host_to_entry(host if host is not None else label, is_host=host is not None)
    token = context.set_active(entry)
    try:
        yield entry
    finally:
        context.reset_active(token)


def _host_to_entry(value, is_host=False):
    """Resolve a label or literal host string to a ``ResolvedEntry``.

    For a wildcard host (a concrete host under a ``*`` entry), synthesise an
    entry carrying that literal host and the wildcard's URLconf so
    ``use_host(host="tenant.example.com")`` reverses into it (BR-HOSTMAP-009).
    """
    from hostmap.map import ResolvedEntry

    entries = hostmap_map.resolved_entries()

    if not is_host and value in entries:
        return entries[value]

    # Treat value as a literal host: exact match first.
    normalised = hostmap_map._strip_port(str(value))
    for entry in entries.values():
        if not entry.wildcard and entry.host == normalised:
            return entry

    # Wildcard synthesis: the concrete host borrows the wildcard's URLconf.
    for entry in entries.values():
        if entry.wildcard and hostmap_map._wildcard_matches(entry, normalised):
            return ResolvedEntry(
                label=entry.label,
                host=normalised,
                urlconf=entry.urlconf,
                redirect_to=None,
                wildcard=False,
            )

    raise NoReverseMatch(f"use_host: {value!r} does not match any hostmap entry or host.")


# ``get_script_prefix`` is imported for the seam self-test (apps.py) to reverse
# a probe pattern through the same script-prefix machinery stock reverse uses.
__all__ = ["reverse", "build_absolute_uri", "use_host", "get_script_prefix"]
