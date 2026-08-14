"""Pins the private Django resolver seam the reverse patch depends on.

``resolvers.HostAwareResolver._reverse_with_prefix`` (03-services.md section 2)
overrides ``URLResolver._reverse_with_prefix``, a private Django API. These
tests fail loudly, independent of any hostmap runtime behaviour, if that
method disappears, is renamed, or changes signature, rather than relying on
some other test incidentally exercising the seam and failing obscurely.

icvoss/django-hostmap#9 verified the seam directly against Django 6.1 by
diffing the ``django/urls`` package source against 6.0.8 (byte-identical) and
reading the 6.1 release notes (no resolver/reversing changes); these tests
encode that verification as an executable check so a future Django release
that DOES move the seam is caught here first, before the E009 ceiling check
even runs.
"""

from __future__ import annotations

import inspect

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.urls.resolvers import URLResolver


def test_reverse_with_prefix_exists_on_urlresolver():
    """The seam method must still exist on ``URLResolver``."""
    assert hasattr(URLResolver, "_reverse_with_prefix")
    assert callable(URLResolver._reverse_with_prefix)


def test_reverse_with_prefix_signature_unchanged():
    """The seam's signature must still be ``(self, lookup_view, _prefix, *args, **kwargs)``.

    ``HostAwareResolver._reverse_with_prefix`` (hostmap/resolvers.py) forwards
    positionally to ``super()._reverse_with_prefix(lookup_view, _prefix, *args,
    **kwargs)`` and to the fallback resolvers the same way; a parameter
    reorder, rename, or a new required parameter here would silently break
    that forwarding.
    """
    signature = inspect.signature(URLResolver._reverse_with_prefix)
    params = list(signature.parameters.values())

    names = [p.name for p in params]
    assert names[:3] == ["self", "lookup_view", "_prefix"], names

    kinds = {p.name: p.kind for p in params}
    assert kinds["lookup_view"] == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert kinds["_prefix"] == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params), (
        "seam must still accept *args (positional URL kwargs)"
    )
    assert any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params), (
        "seam must still accept **kwargs (named URL kwargs)"
    )


def test_host_aware_resolver_override_matches_base_signature():
    """``HostAwareResolver._reverse_with_prefix`` must keep the same shape as
    the method it overrides, so the override stays a faithful wrapper."""
    from hostmap.resolvers import HostAwareResolver

    base_params = list(inspect.signature(URLResolver._reverse_with_prefix).parameters)
    override_params = list(inspect.signature(HostAwareResolver._reverse_with_prefix).parameters)
    assert override_params == base_params


def test_seam_self_test_passes_on_the_running_django():
    """``HostmapConfig._seam_self_test`` (apps.py) is the ready()-time guard;
    exercise it directly so a seam break is caught here, not only implicitly
    via ``AppConfig.ready()`` during test collection."""
    from hostmap.apps import HostmapConfig

    config = HostmapConfig.__new__(HostmapConfig)
    try:
        config._seam_self_test()
    except ImproperlyConfigured as exc:  # pragma: no cover - failure path
        raise AssertionError(f"seam self-test failed on the running Django: {exc}") from exc


def test_seam_self_test_is_behavioural_not_signature_only():
    """icvoss/django-hostmap#12: the strengthened self-test proves the seam's
    cross-host reverse actually produces the expected host-prefixed absolute
    URL, and that a same-host reverse stays an unmangled bare path. A
    signature-only probe (calling the method and swallowing NoReverseMatch)
    would pass even if the composed result were wrong; this test would fail
    if ``_seam_self_test`` regressed to that weaker shape, because it drives
    the same throwaway URLconfs the self-test builds internally and checks
    the seam directly, independent of the self-test's own assertions."""
    from django.http import HttpResponse
    from django.urls import path
    from django.urls.resolvers import RegexPattern

    from hostmap import urls as hostmap_urls
    from hostmap.map import ResolvedEntry
    from hostmap.resolvers import HostAwareResolver

    def _probe_view(request):
        return HttpResponse()

    active_urlconf = (path("active/", _probe_view, name="behavioural-active"),)
    fallback_urlconf = (path("fallback/", _probe_view, name="behavioural-fallback"),)

    active_entry = ResolvedEntry(
        label="behavioural-active-entry",
        host="behavioural-active.invalid",
        urlconf=active_urlconf,
        redirect_to=None,
        wildcard=False,
    )
    fallback_entry = ResolvedEntry(
        label="behavioural-fallback-entry",
        host="behavioural-fallback.invalid",
        urlconf=fallback_urlconf,
        redirect_to=None,
        wildcard=False,
    )

    original_entry_order = hostmap_urls.entry_order
    try:
        hostmap_urls.entry_order = lambda: [active_entry, fallback_entry]
        resolver = HostAwareResolver(RegexPattern(r"^/"), active_urlconf)

        assert resolver._reverse_with_prefix("behavioural-active", "/") == "/active/"
        assert (
            resolver._reverse_with_prefix("behavioural-fallback", "/")
            == "https://behavioural-fallback.invalid/fallback/"
        )
    finally:
        hostmap_urls.entry_order = original_entry_order


def test_seam_self_test_catches_a_cross_host_reverse_that_returns_the_wrong_url(monkeypatch):
    """icvoss/django-hostmap#12 negative case: a seam that accepts the call
    and returns a WRONG result (a mangled or mis-hosted URL) rather than
    raising is exactly what a signature-only probe could not catch. Simulate
    such a seam by monkeypatching ``HostAwareResolver._cross_host_reverse``
    to return a plausible-looking but incorrect value, and assert
    ``_seam_self_test`` raises ``ImproperlyConfigured`` rather than passing
    silently."""
    from hostmap.apps import HostmapConfig
    from hostmap.resolvers import HostAwareResolver

    def _wrong_cross_host_reverse(self, lookup_view, _prefix, args, kwargs):
        return "https://the-wrong-host.invalid/also/the-wrong/path/"

    monkeypatch.setattr(HostAwareResolver, "_cross_host_reverse", _wrong_cross_host_reverse)

    config = HostmapConfig.__new__(HostmapConfig)
    with pytest.raises(ImproperlyConfigured, match="unexpected result"):
        config._seam_self_test()


def test_seam_self_test_catches_a_same_host_reverse_that_gets_mangled(monkeypatch):
    """Negative case for the same-host assertion: a seam override that adds
    a host prefix even to a same-host hit (which stock Django never does)
    must be caught, not just a broken cross-host path."""
    from django.urls.resolvers import URLResolver

    from hostmap.apps import HostmapConfig

    original = URLResolver._reverse_with_prefix

    def _mangling_reverse_with_prefix(self, lookup_view, _prefix, *args, **kwargs):
        path = original(self, lookup_view, _prefix, *args, **kwargs)
        return f"https://unexpectedly-mangled.invalid{path}"

    monkeypatch.setattr(URLResolver, "_reverse_with_prefix", _mangling_reverse_with_prefix)

    config = HostmapConfig.__new__(HostmapConfig)
    with pytest.raises(ImproperlyConfigured, match="same-host reverse"):
        config._seam_self_test()
