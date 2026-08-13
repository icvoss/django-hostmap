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
