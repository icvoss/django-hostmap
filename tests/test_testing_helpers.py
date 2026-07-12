"""hostmap.testing helpers: host_client and the use_host re-export.

Covers 04-interfaces.md section 6.
"""

from __future__ import annotations

import pytest

from hostmap.testing import host_client, use_host


def test_host_client_routes_to_the_named_host():
    """host_client('api') returns a client whose requests route to api."""
    client = host_client("api")
    response = client.get("/users/7/")
    assert response.status_code == 200
    assert response.content == b"user 7"


def test_host_client_unknown_label_raises_keyerror():
    """An unknown label raises KeyError naming the known labels."""
    with pytest.raises(KeyError):
        host_client("does-not-exist")


def test_host_client_wildcard_label_raises_valueerror():
    """The wildcard label 'tenant' has no single concrete host."""
    with pytest.raises(ValueError):
        host_client("tenant")


def test_use_host_is_exported_and_callable():
    """hostmap.testing exports use_host as a re-export of the explicit API."""
    assert callable(use_host)
