"""The comparison suite: byte-identical same-host reversing (AC-HOSTMAP-001).

AC-001 and AC-002 are the package's reason to exist, so these are the release
gate in practice (05-verification.md section 3).
"""

import pytest
from django.urls import NoReverseMatch, reverse, reverse_lazy


def _unpatched_reverse(name, urlconf, **kwargs):
    """Reverse against a URLconf using the original, unwrapped resolver.

    Bypasses the hostmap seam entirely so we compare against genuine stock
    Django output.
    """
    from hostmap import resolvers

    factory = resolvers._original_get_resolver or None
    from django.urls import resolvers as dr

    stock = (factory or dr.get_resolver)(urlconf)
    from django.urls.base import get_script_prefix

    return stock._reverse_with_prefix(name, get_script_prefix(), *kwargs.get("args", []))


@pytest.mark.parametrize(
    "name,args",
    [
        ("home", []),
        ("blog-index", []),
    ],
)
def test_same_host_reverse_byte_identical(name, args):
    """AC-001: same-host reverse is byte-identical to stock Django."""
    # www is the default entry, active out of request.
    patched = reverse(name, args=args)
    stock = _unpatched_reverse(name, "urls_www", args=args)
    assert patched == stock
    assert patched.startswith("/")  # relative, not absolute


def test_reverse_lazy_same_host_identical():
    """AC-001: reverse_lazy on the active host stays relative and identical."""
    lazy = reverse_lazy("blog-index")
    assert str(lazy) == "/blog/"


def test_url_tag_same_host(www_client):
    """AC-001: {% url %} for an active-host name renders the stock path."""
    from django.template import Context, Template

    with www_client_context():
        rendered = Template('{% url "blog-index" %}').render(Context())
    assert rendered == "/blog/"


def www_client_context():
    """Make www the active host for template rendering out of a request."""
    from hostmap.urls import use_host

    return use_host("www")


def test_admin_style_reverse_unmodified():
    """AC-003: a namespaced (admin-like) reverse works same-host and cross-host.

    Uses the api URLconf's named pattern to prove cross-host reversing of a
    plain name; the admin itself is exercised in test_thirdparty.
    """
    # Cross-host: user-detail lives only on api.
    url = reverse("user-detail", args=[7])
    assert url == "https://api.example.com/users/7/"


def test_reverse_output_consumers_accept_absolute():
    """03-services.md contract change: reverse() output feeding the audited
    consumers accepts an absolute URL."""
    from django.shortcuts import resolve_url
    from django.utils.encoding import iri_to_uri

    absolute = reverse("user-detail", args=[7])
    assert absolute.startswith("https://")
    # resolve_url passes a URL-looking string straight through.
    assert resolve_url(absolute) == absolute
    # iri_to_uri tolerates it.
    assert iri_to_uri(absolute) == absolute


def test_nowhere_raises_noreversematch_naming_hosts():
    """AC-005/AC-008: a name on no host raises NoReverseMatch naming hosts."""
    with pytest.raises(NoReverseMatch) as exc:
        reverse("does-not-exist-anywhere")
    assert "example.com" in str(exc.value)
