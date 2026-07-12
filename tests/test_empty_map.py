"""Empty HOSTMAP disables all middleware behaviour (BR-HOSTMAP-001).

Regression test: HostmapMiddleware used to raise Http404 on every request
when HOSTMAP was empty, because both match() and default_entry() returned
None. An empty map must instead be a transparent pass-through, per
04-interfaces.md section 2.
"""

from __future__ import annotations

from django.test import Client, override_settings


@override_settings(HOSTMAP={})
def test_empty_hostmap_passes_through_instead_of_404():
    """AC: an empty HOSTMAP serves the request via ROOT_URLCONF, not a 404."""
    from hostmap.map import _parse_cached

    _parse_cached.cache_clear()

    client = Client(SERVER_NAME="www.example.com")
    response = client.get("/")

    assert response.status_code == 200
    assert response.content == b"www home"


@override_settings(HOSTMAP={})
def test_empty_hostmap_does_not_set_request_hostmap():
    """AC: with an empty map, request.hostmap is never set (pass-through)."""
    from django.http import HttpResponse
    from django.test import RequestFactory

    from hostmap.map import _parse_cached
    from hostmap.middleware import HostmapMiddleware

    _parse_cached.cache_clear()

    captured = {}

    def get_response(request):
        captured["request"] = request
        return HttpResponse("ok")

    middleware = HostmapMiddleware(get_response)
    request = RequestFactory().get("/", SERVER_NAME="www.example.com")
    response = middleware(request)

    assert response.status_code == 200
    assert not hasattr(captured["request"], "hostmap")
