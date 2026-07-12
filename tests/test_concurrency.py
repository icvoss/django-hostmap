"""Concurrent host context isolation (BR-HOSTMAP-001, context propagation).

Covers AC-HOSTMAP-016. Full ASGI concurrency is heavy to set up in a unit
test, so this exercises the same guarantee the contextvar gives: each
execution context sees only its own active host, never another's. A
``threading.Barrier`` forces the two contexts to interleave so a leak would
be visible rather than accidentally avoided by sequential execution.
"""

from __future__ import annotations

import threading
from contextvars import copy_context

from hostmap import context
from hostmap.urls import use_host


def test_concurrent_use_host_contexts_do_not_leak():
    """Two threads, each running in its own copied context and each entering
    use_host() for a different label, must each observe only their own
    active label throughout, even when interleaved."""
    barrier = threading.Barrier(2)
    results = {}
    errors = []

    def run(label, key):
        try:
            with use_host(label):
                # Rendezvous with the other thread so both contexts are
                # active at once before either reads its active entry.
                barrier.wait(timeout=5)
                results[key] = context.get_active().label
        except Exception as exc:  # noqa: BLE001 - surfaced via errors list
            errors.append(exc)

    def run_api():
        ctx = copy_context()
        ctx.run(run, "api", "api")

    def run_www():
        ctx = copy_context()
        ctx.run(run, "www", "www")

    thread_api = threading.Thread(target=run_api)
    thread_www = threading.Thread(target=run_www)

    thread_api.start()
    thread_www.start()
    thread_api.join(timeout=5)
    thread_www.join(timeout=5)

    assert not errors, errors
    assert results["api"] == "api"
    assert results["www"] == "www"
