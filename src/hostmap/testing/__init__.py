"""Testing helpers for consuming projects (04-interfaces.md section 6).

Scope is fixed at exactly ``host_client()``, a ``use_host`` re-export, and
pytest fixtures; no request-factory or assertion-helper sprawl (watch flag 3).
"""

from hostmap.testing.helpers import host_client
from hostmap.urls import use_host

__all__ = ["host_client", "use_host"]
