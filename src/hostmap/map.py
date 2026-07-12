"""Host map parsing, resolved entries, and host matching.

The map is a settings dict (01-data-model.md); parsing it yields one
immutable ``ResolvedEntry`` per label. Parsing and per-entry resolver
acquisition are cached so matching and cross-host fallback are cheap
(BR-HOSTMAP-005). The cache is keyed on the map's identity plus the
domain/default settings, so a test that swaps ``settings.HOSTMAP`` rebuilds
transparently.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from hostmap.conf import hostmap_settings

# Keys a valid entry may carry. Any other key is a malformed entry (E001).
_KNOWN_KEYS = frozenset({"host", "subdomain", "urlconf", "redirect_to"})


@dataclass(frozen=True)
class ResolvedEntry:
    """One parsed host map entry.

    ``host`` is the effective host (subdomain joined to the parent domain, or
    the literal ``host`` value). ``wildcard`` is true for ``subdomain: "*"``
    entries. ``redirect_to`` holds the target label for redirect entries and
    is ``None`` otherwise; a redirect entry has no ``urlconf``.
    """

    label: str
    host: str
    urlconf: str | None
    redirect_to: str | None
    wildcard: bool

    @property
    def is_redirect(self) -> bool:
        return self.redirect_to is not None


def effective_host(entry: dict, parent_domain: str) -> str:
    """Return the effective host for a raw entry dict.

    A ``host`` entry uses its literal value. A ``subdomain`` entry joins the
    label to ``parent_domain``; ``""`` means the parent domain itself and
    ``"*"`` yields the wildcard sentinel ``"*.<parent_domain>"``.
    """
    if "host" in entry:
        return str(entry["host"]).lower()
    subdomain = str(entry.get("subdomain", ""))
    if subdomain == "":
        return parent_domain.lower()
    return f"{subdomain}.{parent_domain}".lower()


def _parse(hostmap: dict, parent_domain: str) -> dict[str, ResolvedEntry]:
    """Parse the raw map into an ordered dict of resolved entries.

    Declaration order is preserved (dict insertion order), which
    BR-HOSTMAP-005 relies on for cross-host resolution order. This does not
    validate; system checks (checks.py) own validation. It tolerates a
    malformed entry by skipping it so a misconfiguration surfaces as a check
    error rather than an import-time crash.
    """
    resolved: dict[str, ResolvedEntry] = {}
    for label, entry in hostmap.items():
        if not isinstance(entry, dict):
            continue
        subdomain = entry.get("subdomain")
        resolved[label] = ResolvedEntry(
            label=label,
            host=effective_host(entry, parent_domain),
            urlconf=entry.get("urlconf"),
            redirect_to=entry.get("redirect_to"),
            wildcard=subdomain == "*",
        )
    return resolved


@cache
def _parse_cached(items: tuple, parent_domain: str) -> dict[str, ResolvedEntry]:
    # Rebuild the raw map from the frozen key: each label maps to either its
    # sorted item tuples (a dict entry) or the raw value (a malformed entry).
    raw = {label: (dict(value) if isinstance(value, tuple) else value) for label, value in items}
    return _parse(raw, parent_domain)


def _map_key(hostmap: dict) -> tuple:
    """A hashable snapshot of the raw map for caching.

    Entries are dicts (unhashable), so freeze each into sorted item tuples.
    A non-dict (malformed) entry is carried through verbatim so ``_parse``
    still sees and skips it.
    """
    return tuple(
        (label, tuple(sorted(entry.items())) if isinstance(entry, dict) else entry) for label, entry in hostmap.items()
    )


def resolved_entries() -> dict[str, ResolvedEntry]:
    """Return the resolved entries for the current settings, cached.

    Falls back to an uncached parse if the map contains an unhashable
    malformed value (a list, say); such a map fails a system check anyway.
    """
    hostmap = hostmap_settings.MAP
    parent_domain = hostmap_settings.PARENT_DOMAIN
    try:
        return _parse_cached(_map_key(hostmap), parent_domain)
    except TypeError:
        return _parse(hostmap, parent_domain)


def default_entry() -> ResolvedEntry | None:
    """Return the ``HOSTMAP_DEFAULT`` resolved entry, or ``None`` if unset."""
    entries = resolved_entries()
    return entries.get(hostmap_settings.DEFAULT)


def redirect_target(entry: ResolvedEntry) -> ResolvedEntry | None:
    """Resolve a redirect entry to its (non-redirect) target entry."""
    if entry.redirect_to is None:
        return None
    return resolved_entries().get(entry.redirect_to)


def _strip_port(host: str) -> str:
    """Return ``host`` lowercased with any ``:port`` removed (BR-HOSTMAP-002).

    IPv6 literals are bracketed (``[::1]:8000``); split on the last colon only
    when it falls outside a bracket.
    """
    host = host.lower()
    if host.startswith("["):
        # [ipv6]:port — the port, if any, follows the closing bracket.
        end = host.find("]")
        if end != -1:
            return host[: end + 1]
        return host
    if ":" in host:
        return host.rsplit(":", 1)[0]
    return host


def match(host: str) -> ResolvedEntry | None:
    """Match a request host against the map (BR-HOSTMAP-001, 002).

    Case-insensitive and port-blind. Exact hosts are tried first, then
    wildcard entries (in declaration order). Returns the matched
    ``ResolvedEntry``, or ``None`` when nothing matches (the caller applies
    ``HOSTMAP_UNMATCHED``).
    """
    normalised = _strip_port(host)
    entries = resolved_entries()

    # Exact matches beat wildcards.
    for entry in entries.values():
        if not entry.wildcard and entry.host == normalised:
            return entry

    # Wildcard entries: match a single subdomain level under the parent.
    for entry in entries.values():
        if entry.wildcard and _wildcard_matches(entry, normalised):
            return entry

    return None


def _wildcard_matches(entry: ResolvedEntry, host: str) -> bool:
    """True when ``host`` is a single-level subdomain under the wildcard's parent."""
    # entry.host is "*.<parent_domain>"; the suffix is ".<parent_domain>".
    suffix = entry.host[1:]  # drop the leading "*"
    if not host.endswith(suffix):
        return False
    label = host[: -len(suffix)]
    # Exactly one level: a non-empty label with no further dots.
    return bool(label) and "." not in label


def captured_subdomain(entry: ResolvedEntry, host: str) -> str | None:
    """Return the wildcard label captured from ``host``, or ``None``.

    Only wildcard entries capture a subdomain; for exact entries this is
    always ``None`` (01-data-model.md, ``request.hostmap.subdomain``).
    """
    if not entry.wildcard:
        return None
    normalised = _strip_port(host)
    suffix = entry.host[1:]
    if normalised.endswith(suffix):
        return normalised[: -len(suffix)] or None
    return None
