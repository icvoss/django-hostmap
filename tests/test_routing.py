"""Routing scenarios: host matching, case/port normalisation, wildcards.

Covers AC-HOSTMAP-011, AC-HOSTMAP-013 and BR-HOSTMAP-001/002.
"""

from __future__ import annotations

import pytest
from django.test import Client, override_settings


def test_host_matching_sets_urlconf_per_host(www_client, api_client):
    """AC-011: www and api each serve their own routes (BR-001)."""
    www_response = www_client.get("/")
    assert www_response.status_code == 200
    assert www_response.content == b"www home"

    api_response = api_client.get("/users/7/")
    assert api_response.status_code == 200
    assert api_response.content == b"user 7"


def test_host_matching_is_case_insensitive():
    """AC-011: an upper-case Host header still routes correctly (BR-002)."""
    client = Client(SERVER_NAME="API.EXAMPLE.COM")
    response = client.get("/users/7/")
    assert response.status_code == 200
    assert response.content == b"user 7"


def test_host_matching_ignores_port():
    """AC-011: a Host header carrying a port still matches (BR-002)."""
    client = Client(SERVER_NAME="api.example.com", SERVER_PORT="8443")
    response = client.get("/users/7/")
    assert response.status_code == 200
    assert response.content == b"user 7"


def test_exact_host_beats_wildcard():
    """The exact apex host is not swallowed by the tenant wildcard.

    example.com is an exact ``host`` entry (a redirect); it must be matched
    before the ``*.example.com`` wildcard is even considered.
    """
    client = Client(SERVER_NAME="example.com")
    response = client.get("/anything/")
    assert response.status_code == 301
    assert response["Location"] == "https://www.example.com/anything/"


def test_unmatched_multilevel_subdomain_falls_to_default():
    """AC-011: a.b.example.com matches no exact or wildcard entry and falls
    to the default (www) under HOSTMAP_UNMATCHED='default' (BR-001)."""
    client = Client(SERVER_NAME="a.b.example.com")
    response = client.get("/")
    assert response.status_code == 200
    assert response.content == b"www home"


@pytest.mark.parametrize("unmatched_setting", ["reject"])
def test_unmatched_host_rejected_returns_404(unmatched_setting):
    """AC-011: HOSTMAP_UNMATCHED='reject' returns 404 for a host matching
    nothing, including the wildcard (BR-001)."""
    with override_settings(HOSTMAP_UNMATCHED=unmatched_setting):
        client = Client(SERVER_NAME="x.y.z.example.com")
        response = client.get("/")
    assert response.status_code == 404


def test_unmatched_host_default_still_routes_after_reject_override():
    """Sanity check: the default behaviour returns after the override context
    exits, proving HOSTMAP_UNMATCHED is read live and not cached."""
    client = Client(SERVER_NAME="x.y.z.example.com")
    response = client.get("/")
    assert response.status_code == 200
    assert response.content == b"www home"


def test_wildcard_routes_to_tenant_urlconf_and_captures_subdomain():
    """AC-013: acme.example.com serves urls_tenant; request.hostmap.label ==
    'tenant' and request.hostmap.subdomain == 'acme' (BR-009)."""
    client = Client(SERVER_NAME="acme.example.com")
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert response.content == b"tenant dashboard: acme"


def test_wildcard_request_has_no_bare_subdomain_attribute():
    """BR-009: no bare request.subdomain attribute is ever set.

    Exercised through the middleware directly rather than the view, since
    the view only reads request.hostmap.
    """
    from django.test import RequestFactory

    from hostmap.middleware import HostmapMiddleware

    captured = {}

    def get_response(request):
        captured["request"] = request
        from django.http import HttpResponse

        return HttpResponse("ok")

    middleware = HostmapMiddleware(get_response)
    request = RequestFactory().get("/dashboard/", SERVER_NAME="acme.example.com")
    middleware(request)

    routed_request = captured["request"]
    assert routed_request.hostmap.label == "tenant"
    assert routed_request.hostmap.subdomain == "acme"
    assert not hasattr(routed_request, "subdomain")
