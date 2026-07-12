"""``manage.py hostmap``: prints the resolved map.

Covers 04-interfaces.md section 4.
"""

from __future__ import annotations

import io

from django.core.management import call_command


def test_command_lists_every_entry_host_urlconf_and_redirect_target():
    """The command names each entry's host, the urlconf for non-redirect
    entries, and the redirect target for the apex entry."""
    out = io.StringIO()
    call_command("hostmap", stdout=out)
    output = out.getvalue()

    assert "www.example.com" in output
    assert "urls_www" in output

    assert "api.example.com" in output
    assert "urls_api" in output

    assert "*.example.com" in output

    assert "example.com" in output
    assert "-> www" in output
