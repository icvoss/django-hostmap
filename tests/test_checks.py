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


def test_e009_django_above_tested_ceiling_with_patch_active(monkeypatch):
    """icvoss/django-hostmap#4: hostmap.E009, the running Django exceeds the
    tested ceiling AND the reverse patch is active (HOSTMAP_PATCH_REVERSE
    defaults to True), the risky combination: the patch hooks a private
    Django resolver seam that has not been verified on this Django version.
    This must fail startup (an Error, not a Warning), never boot silently."""
    import hostmap.apps

    monkeypatch.setattr(hostmap.apps, "TESTED_DJANGO_CEILING", (0, 0))
    ids = _errors(HOSTMAP=BASE_MAP, HOSTMAP_DEFAULT="www", HOSTMAP_PARENT_DOMAIN="example.com")
    assert "hostmap.E009" in ids
    assert "hostmap.W004" not in ids


def test_w004_django_above_tested_ceiling_with_patch_disabled(monkeypatch):
    """hostmap.W004: the running Django exceeds the tested ceiling but
    HOSTMAP_PATCH_REVERSE is False (routing-only), so the unverified private
    resolver seam is never touched. This stays a Warning: nothing here is
    actually running unverified, so failing startup would be over-strict."""
    import hostmap.apps

    monkeypatch.setattr(hostmap.apps, "TESTED_DJANGO_CEILING", (0, 0))
    ids = _errors(
        HOSTMAP=BASE_MAP,
        HOSTMAP_DEFAULT="www",
        HOSTMAP_PARENT_DOMAIN="example.com",
        HOSTMAP_PATCH_REVERSE=False,
    )
    assert "hostmap.W004" in ids
    assert "hostmap.E009" not in ids


def test_no_ceiling_problem_when_django_is_within_the_tested_ceiling(monkeypatch):
    """Neither E009 nor W004 fires on a Django version within the declared
    ceiling: the ordinary, unremarkable case.

    Pins the ceiling to the actual running Django version (rather than
    relying on the real installed version being within the package's
    declared ceiling) so this test is deterministic in any environment,
    including one that legitimately runs a newer Django than the package
    has declared support for, exactly like its E009/W004 sibling tests
    already pin the ceiling to force the opposite branch.
    """
    import django

    import hostmap.apps

    monkeypatch.setattr(hostmap.apps, "TESTED_DJANGO_CEILING", django.VERSION[:2])
    ids = _errors(HOSTMAP=BASE_MAP, HOSTMAP_DEFAULT="www", HOSTMAP_PARENT_DOMAIN="example.com")
    assert "hostmap.E009" not in ids
    assert "hostmap.W004" not in ids


def test_hostmap_allow_untested_django_defaults_to_false():
    """HOSTMAP_ALLOW_UNTESTED_DJANGO defaults to False when unset, so the
    E009 refusal is the out-of-the-box behaviour (icvoss/django-hostmap#12).

    Asserted explicitly, against a Django settings module with the setting
    absent, rather than relying on the default implicitly elsewhere.
    """
    from django.conf import settings

    from hostmap.conf import hostmap_settings

    assert not hasattr(settings, "HOSTMAP_ALLOW_UNTESTED_DJANGO")
    assert hostmap_settings.ALLOW_UNTESTED_DJANGO is False


def test_e009_still_fires_when_allow_untested_django_is_false(monkeypatch):
    """HOSTMAP_ALLOW_UNTESTED_DJANGO = False (the default) leaves the
    original E009 refusal unchanged: back-compatible with pre-#12 startup
    behaviour when the setting is absent or explicitly off."""
    import hostmap.apps

    monkeypatch.setattr(hostmap.apps, "TESTED_DJANGO_CEILING", (0, 0))
    ids = _errors(
        HOSTMAP=BASE_MAP,
        HOSTMAP_DEFAULT="www",
        HOSTMAP_PARENT_DOMAIN="example.com",
        HOSTMAP_ALLOW_UNTESTED_DJANGO=False,
    )
    assert "hostmap.E009" in ids
    assert "hostmap.W005" not in ids


def test_w005_when_allow_untested_django_is_true_and_patch_active(monkeypatch):
    """icvoss/django-hostmap#12: HOSTMAP_ALLOW_UNTESTED_DJANGO = True downgrades
    hostmap.E009 to hostmap.W005, an explicit, opt-in acceptance of an
    unverified Django version running the reverse patch. Startup proceeds;
    the ready()-time seam self-test remains the live guard regardless."""
    import hostmap.apps

    monkeypatch.setattr(hostmap.apps, "TESTED_DJANGO_CEILING", (0, 0))
    ids = _errors(
        HOSTMAP=BASE_MAP,
        HOSTMAP_DEFAULT="www",
        HOSTMAP_PARENT_DOMAIN="example.com",
        HOSTMAP_ALLOW_UNTESTED_DJANGO=True,
    )
    assert "hostmap.W005" in ids
    assert "hostmap.E009" not in ids
    assert "hostmap.W004" not in ids


def test_w004_unaffected_by_allow_untested_django_when_patch_is_off(monkeypatch):
    """Routing-only (HOSTMAP_PATCH_REVERSE = False) keeps the existing softer
    hostmap.W004 regardless of HOSTMAP_ALLOW_UNTESTED_DJANGO: the opt-out
    setting only matters when the patch is actually active."""
    import hostmap.apps

    monkeypatch.setattr(hostmap.apps, "TESTED_DJANGO_CEILING", (0, 0))
    ids = _errors(
        HOSTMAP=BASE_MAP,
        HOSTMAP_DEFAULT="www",
        HOSTMAP_PARENT_DOMAIN="example.com",
        HOSTMAP_PATCH_REVERSE=False,
        HOSTMAP_ALLOW_UNTESTED_DJANGO=True,
    )
    assert "hostmap.W004" in ids
    assert "hostmap.E009" not in ids
    assert "hostmap.W005" not in ids
