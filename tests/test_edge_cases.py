"""Edge-case acceptance criteria the engineering panel flagged as untested.

AC-HOSTMAP-006 (FORCE_SCRIPT_NAME script-prefix composition) and
AC-HOSTMAP-007 (i18n_patterns per-host routing and reversing), plus a guard
that the two resolution paths (explicit API and resolver seam) agree, so
watch flag 2 (one code path) cannot silently drift.
"""

import pytest
from django.test import override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import translation


def _clear_caches():
    """Rebuild the map and resolver caches after a settings override."""
    from hostmap import resolvers
    from hostmap.map import _parse_cached

    _parse_cached.cache_clear()
    resolvers._host_aware_resolver.cache_clear()


# --- AC-HOSTMAP-006: FORCE_SCRIPT_NAME -------------------------------------


@override_settings(FORCE_SCRIPT_NAME="/app")
def test_force_script_name_same_host():
    """AC-006: the script prefix prepends to same-host reverses."""
    from django.urls.base import set_script_prefix

    _clear_caches()
    # FORCE_SCRIPT_NAME is applied by Django's request handling; out of a
    # request we set the prefix explicitly, mirroring what the handler does.
    set_script_prefix("/app/")
    try:
        assert reverse("home") == "/app/"
        assert reverse("blog-index") == "/app/blog/"
    finally:
        set_script_prefix("/")


@override_settings(FORCE_SCRIPT_NAME="/app")
def test_force_script_name_cross_host():
    """AC-006: cross-host absolute URLs compose the script prefix correctly."""
    from django.urls.base import set_script_prefix

    _clear_caches()
    set_script_prefix("/app/")
    try:
        # The script prefix lands in the path, after the authority.
        assert reverse("user-detail", args=[7]) == "https://api.example.com/app/users/7/"
    finally:
        set_script_prefix("/")


# --- AC-HOSTMAP-007: i18n_patterns -----------------------------------------

I18N_MAP = {
    "www": {"subdomain": "www", "urlconf": "urls_www"},
    "api": {"subdomain": "api", "urlconf": "urls_api"},
    "intl": {"subdomain": "intl", "urlconf": "urls_i18n"},
}


@override_settings(HOSTMAP=I18N_MAP, USE_I18N=True, LANGUAGE_CODE="en")
def test_i18n_patterns_route(client):
    """AC-007: a per-host URLconf using i18n_patterns routes with a locale prefix."""
    _clear_caches()
    # i18n_patterns serves the default language at its prefixed path.
    response = client.get("/en/account/", SERVER_NAME="intl.example.com")
    assert response.status_code == 200
    assert response.content == b"account"


@override_settings(HOSTMAP=I18N_MAP, USE_I18N=True, LANGUAGE_CODE="en")
def test_i18n_patterns_reverse_cross_host():
    """AC-007: reversing a name in an i18n_patterns host works cross-host."""
    _clear_caches()
    with translation.override("en"):
        url = reverse("i18n-account")
    # Reversed cross-host from www: absolute, locale-prefixed.
    assert url == "https://intl.example.com/en/account/"


# --- Watch flag 2: the two paths agree -------------------------------------


@pytest.mark.parametrize(
    "name,args",
    [
        ("home", None),
        ("blog-index", None),
        ("user-detail", [7]),
    ],
)
def test_seam_and_explicit_api_agree(name, args):
    """The patched stock reverse() and hostmap.urls.reverse() return the same URL.

    Guards watch flag 2: both consume urls.entry_order(), so if a future change
    forked the ordering the two would diverge and this would fail.
    """
    from hostmap.urls import reverse as explicit_reverse

    stock = reverse(name, args=args)
    explicit = explicit_reverse(name, args=args)
    assert stock == explicit


def test_seam_and_explicit_api_agree_on_failure():
    """Both paths raise NoReverseMatch naming the searched hosts for an unknown name."""
    from hostmap.urls import reverse as explicit_reverse

    with pytest.raises(NoReverseMatch) as stock_exc:
        reverse("no-such-name-anywhere")
    with pytest.raises(NoReverseMatch) as explicit_exc:
        explicit_reverse("no-such-name-anywhere")
    assert "example.com" in str(stock_exc.value)
    assert "example.com" in str(explicit_exc.value)
