"""HostmapMiddleware: per-host URLconf, active-host context, request.hostmap.

Implements BR-HOSTMAP-001, 002 (routing) and BR-HOSTMAP-008 (redirect
entries). Must sit before ``CommonMiddleware``, whose ``APPEND_SLASH``
resolves against the request's URLconf (03-services.md section 1).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.http import Http404, HttpResponsePermanentRedirect, HttpResponseRedirect

from hostmap import context
from hostmap import map as hostmap_map
from hostmap.conf import hostmap_settings


@dataclass(frozen=True)
class HostmapInfo:
    """The namespaced ``request.hostmap`` object (01-data-model.md).

    Kept deliberately at two attributes; no bare ``request.subdomain`` is set,
    which django-subdomains and other middleware historically claimed
    (BR-HOSTMAP-009).
    """

    label: str
    subdomain: str | None = None


class HostmapMiddleware:
    """Route each request by host and record the active entry."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not hostmap_map.resolved_entries():
            # An empty HOSTMAP disables all hostmap behaviour: no urlconf
            # override, no request.hostmap, no active-host context. This
            # keeps it safe to install the middleware unconditionally (a
            # shared settings base) with the map configured per environment
            # (04-interfaces.md section 2; BR-HOSTMAP-001).
            return self.get_response(request)

        entry = self._resolve_entry(request)

        if entry is None:
            # No match and HOSTMAP_UNMATCHED == "reject".
            raise Http404("Host does not match any hostmap entry.")

        if entry.is_redirect:
            return self._redirect(request, entry)

        request.urlconf = entry.urlconf
        request.hostmap = HostmapInfo(
            label=entry.label,
            subdomain=hostmap_map.captured_subdomain(entry, request.get_host()),
        )

        token = context.set_active(entry)
        try:
            return self.get_response(request)
        finally:
            context.reset_active(token)

    def _resolve_entry(self, request):
        """Match the host, applying ``HOSTMAP_UNMATCHED`` on no match."""
        entry = hostmap_map.match(request.get_host())
        if entry is not None:
            return entry
        if hostmap_settings.UNMATCHED == "reject":
            return None
        return hostmap_map.default_entry()

    def _redirect(self, request, entry):
        """Redirect to the same path and query on the target host (BR-HOSTMAP-008)."""
        from hostmap.urls import build_absolute_uri

        target = hostmap_map.redirect_target(entry)
        # Preserve the full path including the query string. ``host`` accepts a
        # label; the target is always a non-redirect entry (E004 forbids chains).
        location = build_absolute_uri(request.get_full_path(), host=target.label if target else None)
        if hostmap_settings.REDIRECT_PERMANENT:
            return HttpResponsePermanentRedirect(location)
        return HttpResponseRedirect(location)
