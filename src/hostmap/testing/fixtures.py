"""pytest fixtures for hostmap (04-interfaces.md section 6).

Import into a project's ``conftest.py`` with::

    from hostmap.testing.fixtures import *  # noqa: F401,F403
"""

from __future__ import annotations

import pytest

from hostmap.testing.helpers import host_client as _host_client


@pytest.fixture
def host_client():
    """Factory fixture: ``host_client("api")`` returns a host-bound test client."""
    return _host_client
