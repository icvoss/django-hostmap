"""``host_client(label)``: a Django test client wired to a hostmap host."""

from __future__ import annotations

from django.test import Client

from hostmap.map import resolved_entries


def host_client(label: str, **kwargs) -> Client:
    """Return a Django test :class:`~django.test.Client` bound to an entry's host.

    Sets ``SERVER_NAME`` to the entry's effective host so every request the
    client makes routes to that host through ``HostmapMiddleware``. Extra
    keyword arguments pass through to ``Client``.

    Usage::

        client = host_client("api")
        response = client.get("/users/7/")
    """
    entries = resolved_entries()
    if label not in entries:
        raise KeyError(f"host_client: '{label}' is not a HOSTMAP label. Known labels: {sorted(entries)}.")
    entry = entries[label]
    # A wildcard entry has no single concrete host; require an explicit host.
    if entry.wildcard:
        raise ValueError(
            f"host_client: '{label}' is a wildcard entry with no single host; "
            "pass SERVER_NAME to a plain Client for the concrete host you want."
        )
    kwargs.setdefault("SERVER_NAME", entry.host)
    return Client(**kwargs)
