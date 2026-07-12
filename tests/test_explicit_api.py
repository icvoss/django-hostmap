"""The explicit API: hostmap.urls.reverse, build_absolute_uri, use_host.

Covers AC-HOSTMAP-004, AC-HOSTMAP-009, AC-HOSTMAP-010, BR-HOSTMAP-004/006
and 03-services.md section 3.
"""

from __future__ import annotations

from django.test import override_settings

from hostmap.urls import build_absolute_uri, reverse, use_host


def test_reverse_same_host_relative():
    """03-services.md section 3: reversing an active-host name stays relative."""
    with use_host("www"):
        assert reverse("home") == "/"


def test_reverse_cross_host_absolute():
    """03-services.md section 3: reversing a name on another host returns an
    absolute URL."""
    with use_host("www"):
        url = reverse("user-detail", args=[7])
    assert url == "https://api.example.com/users/7/"


def test_build_absolute_uri_always_absolute_for_a_name():
    """build_absolute_uri always returns an absolute URL for a URL name,
    even when the name resolves on the active host."""
    with use_host("www"):
        url = build_absolute_uri("home")
    assert url == "https://www.example.com/"


def test_build_absolute_uri_with_ready_made_path():
    """A path (starting with '/') is composed against the active host."""
    with use_host("api"):
        url = build_absolute_uri("/users/7/")
    assert url == "https://api.example.com/users/7/"


def test_build_absolute_uri_with_host_pins_entry():
    """host= pins resolution to a specific entry regardless of what is active."""
    with use_host("www"):
        url = build_absolute_uri("user-detail", args=[7], host="api")
    assert url == "https://api.example.com/users/7/"


def test_use_host_api_makes_relative_reverse_relative():
    """use_host('api') makes api active: reverse('user-detail') is relative,
    and reverse('home') crosses back to the absolute www URL."""
    with use_host("api"):
        assert reverse("user-detail", args=[7]) == "/users/7/"
        assert reverse("home") == "https://www.example.com/"


def test_use_host_with_wildcard_concrete_host():
    """use_host(host=...) on a wildcard's concrete host resolves relative
    URLs against that host's URLconf (BR-009)."""
    with use_host(host="acme.example.com"):
        assert reverse("tenant-dashboard") == "/dashboard/"


def test_out_of_request_default_reverse_uses_www():
    """AC-010: with no use_host active, reverse('home') uses the default
    entry (www) and is relative (BR-006)."""
    assert reverse("home") == "/"


def test_scheme_and_port_overrides_take_effect_immediately():
    """HOSTMAP_SCHEME and HOSTMAP_PORT are read live; overriding them changes
    build_absolute_uri output without any cache invalidation, since the
    resolver cache keys only on map identity and parent domain."""
    with override_settings(HOSTMAP_PORT="8000", HOSTMAP_SCHEME="http"):
        url = build_absolute_uri("user-detail", args=[7], host="api")
    assert url == "http://api.example.com:8000/users/7/"


def test_scheme_and_port_revert_after_override():
    """The scheme/port revert to their configured values once the override
    context exits, confirming no stale cache leaked the override."""
    url = build_absolute_uri("user-detail", args=[7], host="api")
    assert url == "https://api.example.com/users/7/"
