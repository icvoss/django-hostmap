"""A simulated third-party app.

It binds ``reverse`` and ``reverse_lazy`` from ``django.urls`` at module import
time, before ``hostmap.ready()`` runs, exactly as a real third-party package
would (AC-HOSTMAP-002, 009). The seam must make these host-aware without the
app changing anything.
"""

from django.urls import reverse, reverse_lazy  # noqa: F401  bound at import time

# A module-level lazy reverse into another host, resolved on first use.
API_USER_1_LAZY = reverse_lazy("user-detail", args=[1])


def cross_host_link():
    """Call the early-bound ``reverse`` for a name that only exists on api."""
    return reverse("user-detail", args=[7])
