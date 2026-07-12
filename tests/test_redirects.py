"""Redirect entry behaviour: path/query preservation, 301/302 toggle.

Covers AC-HOSTMAP-012 and BR-HOSTMAP-008.
"""

from __future__ import annotations

from django.test import Client, override_settings


def test_apex_redirects_to_www_same_path():
    """AC-012: example.com redirects to https://www.example.com/ (BR-008)."""
    client = Client(SERVER_NAME="example.com")
    response = client.get("/")
    assert response.status_code == 301
    assert response["Location"] == "https://www.example.com/"


def test_apex_redirect_preserves_path_and_query():
    """AC-012: the redirect target keeps the original path and query string."""
    client = Client(SERVER_NAME="example.com")
    response = client.get("/blog/", {"x": "1", "y": "2"})
    assert response.status_code == 301
    assert response["Location"] == "https://www.example.com/blog/?x=1&y=2"


def test_redirect_permanent_false_yields_302():
    """AC-012: HOSTMAP_REDIRECT_PERMANENT=False switches to a 302 (BR-008)."""
    with override_settings(HOSTMAP_REDIRECT_PERMANENT=False):
        client = Client(SERVER_NAME="example.com")
        response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "https://www.example.com/"


def test_redirect_reverts_to_301_after_override():
    """The permanent-redirect default is read live, not cached from the
    previous test's override."""
    client = Client(SERVER_NAME="example.com")
    response = client.get("/")
    assert response.status_code == 301


def test_redirect_entry_answers_every_path():
    """AC-012: a redirect entry answers every path on its host, not just
    the ones with named routes (BR-008)."""
    client = Client(SERVER_NAME="example.com")
    response = client.get("/anything/deep/")
    assert response.status_code == 301
    assert response["Location"] == "https://www.example.com/anything/deep/"
