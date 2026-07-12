"""System checks: one test per hostmap.E00x / hostmap.W00x condition.

Covers AC-HOSTMAP-017 and 04-interfaces.md section 3.
"""

from __future__ import annotations

from django.test import override_settings

from hostmap.checks import check_hostmap
from hostmap.map import _parse_cached

BASE_MAP = {
    "www": {"subdomain": "www", "urlconf": "urls_www"},
    "api": {"subdomain": "api", "urlconf": "urls_api"},
}


def _errors(**settings_overrides):
    """Run check_hostmap under the given settings overrides, clearing the
    map cache first so resolved_entries() rebuilds against the override."""
    with override_settings(**settings_overrides):
        _parse_cached.cache_clear()
        errors = check_hostmap(None)
        _parse_cached.cache_clear()
    return [e.id for e in errors]


def test_e001_entry_not_a_dict():
    """hostmap.E001: an entry that is not a dict."""
    ids = _errors(HOSTMAP={"www": "not-a-dict"}, HOSTMAP_DEFAULT="www")
    assert "hostmap.E001" in ids


def test_e001_entry_empty_dict():
    """hostmap.E001: an empty entry dict."""
    ids = _errors(HOSTMAP={"www": {}}, HOSTMAP_DEFAULT="www")
    assert "hostmap.E001" in ids


def test_e001_entry_unknown_key():
    """hostmap.E001: an entry with a key outside the known set."""
    ids = _errors(
        HOSTMAP={"www": {"subdomain": "www", "urlconf": "urls_www", "bogus": "x"}},
        HOSTMAP_DEFAULT="www",
    )
    assert "hostmap.E001" in ids


def test_e002_both_host_and_subdomain():
    """hostmap.E002: an entry setting both host and subdomain."""
    ids = _errors(
        HOSTMAP={"www": {"host": "example.com", "subdomain": "www", "urlconf": "urls_www"}},
        HOSTMAP_DEFAULT="www",
    )
    assert "hostmap.E002" in ids


def test_e002_neither_host_nor_subdomain():
    """hostmap.E002: an entry setting neither host nor subdomain."""
    ids = _errors(HOSTMAP={"www": {"urlconf": "urls_www"}}, HOSTMAP_DEFAULT="www")
    assert "hostmap.E002" in ids


def test_e003_both_urlconf_and_redirect_to():
    """hostmap.E003: an entry setting both urlconf and redirect_to."""
    ids = _errors(
        HOSTMAP={
            "www": {"subdomain": "www", "urlconf": "urls_www", "redirect_to": "www"},
        },
        HOSTMAP_DEFAULT="www",
    )
    assert "hostmap.E003" in ids


def test_e003_neither_urlconf_nor_redirect_to():
    """hostmap.E003: an entry setting neither urlconf nor redirect_to."""
    ids = _errors(HOSTMAP={"www": {"subdomain": "www"}}, HOSTMAP_DEFAULT="www")
    assert "hostmap.E003" in ids


def test_e004_redirect_to_unknown_label():
    """hostmap.E004: redirect_to names a label that does not exist."""
    ids = _errors(
        HOSTMAP={
            **BASE_MAP,
            "apex": {"host": "example.com", "redirect_to": "nowhere"},
        },
        HOSTMAP_DEFAULT="www",
        HOSTMAP_PARENT_DOMAIN="example.com",
    )
    assert "hostmap.E004" in ids


def test_e004_redirect_to_another_redirect_chains():
    """hostmap.E004: redirect_to names another redirect entry (a chain)."""
    ids = _errors(
        HOSTMAP={
            **BASE_MAP,
            "apex": {"host": "example.com", "redirect_to": "apex2"},
            "apex2": {"host": "example.org", "redirect_to": "www"},
        },
        HOSTMAP_DEFAULT="www",
        HOSTMAP_PARENT_DOMAIN="example.com",
    )
    assert "hostmap.E004" in ids


def test_e005_default_unset():
    """hostmap.E005: HOSTMAP_DEFAULT is unset while the map is non-empty."""
    ids = _errors(HOSTMAP=BASE_MAP, HOSTMAP_DEFAULT="")
    assert "hostmap.E005" in ids


def test_e005_default_not_a_label():
    """hostmap.E005: HOSTMAP_DEFAULT names a label absent from the map."""
    ids = _errors(HOSTMAP=BASE_MAP, HOSTMAP_DEFAULT="nonexistent")
    assert "hostmap.E005" in ids


def test_e006_unimportable_urlconf():
    """hostmap.E006: an entry's urlconf cannot be imported."""
    ids = _errors(
        HOSTMAP={"www": {"subdomain": "www", "urlconf": "this.module.does.not.exist"}},
        HOSTMAP_DEFAULT="www",
    )
    assert "hostmap.E006" in ids


def test_e007_duplicate_effective_hosts():
    """hostmap.E007: two entries resolve to the same effective host."""
    ids = _errors(
        HOSTMAP={
            "www": {"subdomain": "www", "urlconf": "urls_www"},
            "www2": {"subdomain": "www", "urlconf": "urls_api"},
        },
        HOSTMAP_DEFAULT="www",
        HOSTMAP_PARENT_DOMAIN="example.com",
    )
    assert "hostmap.E007" in ids


def test_e008_subdomain_entry_without_parent_domain():
    """hostmap.E008: a subdomain entry with HOSTMAP_PARENT_DOMAIN unset."""
    ids = _errors(HOSTMAP=BASE_MAP, HOSTMAP_DEFAULT="www", HOSTMAP_PARENT_DOMAIN="")
    assert "hostmap.E008" in ids


def test_w001_mapped_host_not_in_allowed_hosts():
    """hostmap.W001: a mapped host outside a narrow ALLOWED_HOSTS."""
    ids = _errors(
        HOSTMAP=BASE_MAP,
        HOSTMAP_DEFAULT="www",
        HOSTMAP_PARENT_DOMAIN="example.com",
        ALLOWED_HOSTS=["completely-different.example.net"],
    )
    assert "hostmap.W001" in ids


def test_w001_not_raised_when_allowed_hosts_is_wildcard():
    """ALLOWED_HOSTS = ['*'] short-circuits the W001 check entirely."""
    ids = _errors(
        HOSTMAP=BASE_MAP,
        HOSTMAP_DEFAULT="www",
        HOSTMAP_PARENT_DOMAIN="example.com",
        ALLOWED_HOSTS=["*"],
    )
    assert "hostmap.W001" not in ids


def test_w002_middleware_missing():
    """hostmap.W002: HOSTMAP configured without HostmapMiddleware installed."""
    ids = _errors(
        HOSTMAP=BASE_MAP,
        HOSTMAP_DEFAULT="www",
        HOSTMAP_PARENT_DOMAIN="example.com",
        MIDDLEWARE=["django.middleware.common.CommonMiddleware"],
    )
    assert "hostmap.W002" in ids


def test_w003_root_urlconf_mismatch():
    """hostmap.W003: ROOT_URLCONF does not match the default entry's urlconf."""
    ids = _errors(
        HOSTMAP=BASE_MAP,
        HOSTMAP_DEFAULT="www",
        HOSTMAP_PARENT_DOMAIN="example.com",
        ROOT_URLCONF="urls_api",
    )
    assert "hostmap.W003" in ids


def test_w004_django_above_tested_ceiling(monkeypatch):
    """hostmap.W004: the running Django exceeds the tested ceiling."""
    import hostmap.apps

    monkeypatch.setattr(hostmap.apps, "TESTED_DJANGO_CEILING", (0, 0))
    ids = _errors(HOSTMAP=BASE_MAP, HOSTMAP_DEFAULT="www", HOSTMAP_PARENT_DOMAIN="example.com")
    assert "hostmap.W004" in ids
