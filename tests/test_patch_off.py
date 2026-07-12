"""HOSTMAP_PATCH_REVERSE off: the resolver seam is removable (BR-HOSTMAP-007).

Covers AC-HOSTMAP-014. HOSTMAP_PATCH_REVERSE is only read at ready(), so this
drives resolvers.uninstall()/install() directly rather than restarting the
app registry.
"""

from __future__ import annotations

import pytest
from django.urls import NoReverseMatch
from django.urls import reverse as stock_reverse

from hostmap import resolvers
from hostmap.testing import host_client, use_host
from hostmap.urls import reverse as hostmap_reverse


@pytest.fixture
def patch_uninstalled():
    """Uninstall the resolver seam for the duration of a test, then restore it.

    install()/uninstall() are idempotent, but the fixture always leaves the
    seam installed afterwards so other tests are unaffected.
    """
    resolvers.uninstall()
    try:
        yield
    finally:
        resolvers.install()


def test_stock_reverse_has_no_cross_host_fallback_when_uninstalled(patch_uninstalled):
    """AC-014: with the seam uninstalled, stock reverse() for a name that
    only exists on another host raises NoReverseMatch instead of falling
    back cross-host."""
    with use_host("www"), pytest.raises(NoReverseMatch):
        stock_reverse("user-detail", args=[7])


def test_routing_still_works_when_patch_uninstalled(patch_uninstalled):
    """AC-014: routing (the middleware / host_client) is unaffected by the
    reverse patch being uninstalled."""
    client = host_client("api")
    response = client.get("/users/7/")
    assert response.status_code == 200
    assert response.content == b"user 7"


def test_explicit_api_still_cross_host_reverses_when_patch_uninstalled(patch_uninstalled):
    """AC-014: the explicit API (hostmap.urls.reverse) keeps working even
    when the stock reverse() patch is uninstalled; it never depended on the
    seam being installed."""
    with use_host("www"):
        url = hostmap_reverse("user-detail", args=[7])
    assert url == "https://api.example.com/users/7/"
