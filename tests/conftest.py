"""Shared fixtures for the django-hostmap test suite."""

import pytest


@pytest.fixture
def www_client():
    from hostmap.testing import host_client

    return host_client("www")


@pytest.fixture
def api_client():
    from hostmap.testing import host_client

    return host_client("api")


@pytest.fixture(autouse=True)
def _reset_hostmap_caches():
    """Clear map and resolver caches between tests that mutate settings."""
    from hostmap import resolvers
    from hostmap.map import _parse_cached

    yield
    _parse_cached.cache_clear()
    resolvers._host_aware_resolver.cache_clear()
