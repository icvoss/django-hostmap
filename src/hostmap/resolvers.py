"""The resolver seam: host-aware cross-host fallback under stock ``reverse()``.

Why patching ``reverse`` alone cannot work (03-services.md section 2):
third-party apps bind ``from django.urls import reverse`` at their own import
time, before any ``AppConfig.ready()`` runs, so rebinding
``django.urls.reverse`` afterwards does not affect those references. The
integration must sit at a seam every call passes through dynamically.

The chosen seam is resolver acquisition. ``django.urls.base.reverse`` calls
``get_resolver(urlconf)`` on every call and then
``resolver._reverse_with_prefix(...)``. We wrap ``get_resolver`` so that, for
the active host's URLconf, it returns a :class:`HostAwareResolver`, a
``URLResolver`` subclass whose ``_reverse_with_prefix`` retries the other
hosts' resolvers on ``NoReverseMatch`` and returns an absolute URL for a
cross-host match. Non-active URLconfs get the ordinary stock resolver, so the
fallback targets never wrap and the search cannot recurse. Same-host
reversing is untouched and stays byte-identical (BR-HOSTMAP-003).

Installed and removed at ``AppConfig.ready()`` and gated by
``HOSTMAP_PATCH_REVERSE`` (BR-HOSTMAP-007).
"""

from __future__ import annotations

from functools import cache

from django.urls import NoReverseMatch
from django.urls import resolvers as django_resolvers
from django.urls.resolvers import RegexPattern, URLResolver

# The stock resolver factory we wrap, captured at install time so uninstall
# restores exactly what was there. ``None`` means "not installed".
_original_get_resolver = None


class HostAwareResolver(URLResolver):
    """A ``URLResolver`` that falls back to other hosts on ``NoReverseMatch``.

    Only the active host's URLconf is ever wrapped in this class; the per-host
    resolvers it retries during fallback are plain stock resolvers, so there is
    no recursion.
    """

    def _reverse_with_prefix(self, lookup_view, _prefix, *args, **kwargs):
        try:
            return super()._reverse_with_prefix(lookup_view, _prefix, *args, **kwargs)
        except NoReverseMatch:
            return self._cross_host_reverse(lookup_view, _prefix, args, kwargs)

    def _cross_host_reverse(self, lookup_view, _prefix, args, kwargs):
        from hostmap import context
        from hostmap import map as hostmap_map
        from hostmap.urls import _absolute_url, logger

        active = context.get_active()
        active_label = active.label if active is not None else None

        for entry in _fallback_entries(active_label):
            resolver = _stock_resolver(entry.urlconf)
            try:
                path = resolver._reverse_with_prefix(lookup_view, _prefix, *args, **kwargs)
            except NoReverseMatch:
                continue
            logger.debug("hostmap cross-host reverse: %r -> host %s (%s)", lookup_view, entry.host, entry.label)
            return _absolute_url(entry, path)

        searched = ", ".join(e.host for e in hostmap_map.resolved_entries().values()) or "(no hostmap entries)"
        raise NoReverseMatch(f"Reverse for '{lookup_view}' not found on any hostmap host. Searched: {searched}.")


def _fallback_entries(active_label):
    """Non-active, non-redirect, non-wildcard entries in BR-HOSTMAP-005 order."""
    from hostmap import map as hostmap_map

    entries = hostmap_map.resolved_entries()
    default = hostmap_map.default_entry()
    ordered = []
    seen = set()
    if active_label is not None:
        seen.add(active_label)

    def _add(entry):
        if entry is None or entry.label in seen or entry.is_redirect or entry.wildcard:
            return
        seen.add(entry.label)
        ordered.append(entry)

    _add(default)
    for entry in entries.values():
        _add(entry)
    return ordered


def _stock_resolver(urlconf):
    """A plain (unwrapped) stock ``URLResolver`` for ``urlconf``.

    Uses the original ``get_resolver`` so the fallback resolvers are ordinary
    resolvers, never ``HostAwareResolver`` (which would recurse). Django caches
    these, so this is a single cheap dict lookup after the first call
    (BR-HOSTMAP-005).
    """
    factory = _original_get_resolver or django_resolvers.get_resolver
    return factory(urlconf)


@cache
def _host_aware_resolver(urlconf) -> HostAwareResolver:
    """Build (once per URLconf) a ``HostAwareResolver`` for the active host.

    A distinct object from Django's cached stock resolver, so the stock cache
    is never mutated and fallback resolvers stay plain. Cached here so the
    active resolver is built once, not per ``reverse()`` call.
    """
    return HostAwareResolver(RegexPattern(r"^/"), urlconf)


def install():
    """Wrap ``get_resolver`` so the active URLconf acquires a ``HostAwareResolver``.

    Idempotent. The wrapper returns the host-aware resolver only for the active
    host's URLconf (or the default entry's, out of request); every other
    URLconf, including the fallback targets, gets the ordinary stock resolver.
    """
    global _original_get_resolver
    if _original_get_resolver is not None:
        return  # already installed

    _original_get_resolver = django_resolvers.get_resolver

    def hostmap_get_resolver(urlconf=None):
        target = urlconf if urlconf is not None else _root_urlconf()
        if _is_active_urlconf(target):
            return _host_aware_resolver(target)
        return _original_get_resolver(urlconf)

    django_resolvers.get_resolver = hostmap_get_resolver
    _patch_base_reference(hostmap_get_resolver)


def uninstall():
    """Restore the original ``get_resolver``; routing keeps working (BR-HOSTMAP-007)."""
    global _original_get_resolver
    if _original_get_resolver is None:
        return
    django_resolvers.get_resolver = _original_get_resolver
    _patch_base_reference(_original_get_resolver)
    _original_get_resolver = None
    _host_aware_resolver.cache_clear()


def is_installed() -> bool:
    return _original_get_resolver is not None


def _is_active_urlconf(urlconf) -> bool:
    """True when ``urlconf`` is the active entry's URLconf.

    Out of request the active entry is the ``HOSTMAP_DEFAULT`` entry, so
    import-time and out-of-request reversing (against ROOT_URLCONF) is
    host-aware too (BR-HOSTMAP-006).
    """
    from hostmap import context

    active = context.get_active()
    return active is not None and not active.is_redirect and urlconf == active.urlconf


def _root_urlconf():
    from django.conf import settings

    return settings.ROOT_URLCONF


def _patch_base_reference(factory):
    """Point ``django.urls.base``'s ``get_resolver`` at ``factory``.

    ``django.urls.base.reverse`` imports ``get_resolver`` into its own module
    namespace, so replacing only ``resolvers.get_resolver`` is not enough.
    """
    from django.urls import base

    base.get_resolver = factory
