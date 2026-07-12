"""Django system checks for hostmap configuration (04-interfaces.md section 3).

Registered in ``AppConfig.ready()`` and run at startup and during test
collection. Errors (E001-E008) fail startup; warnings (W001-W004) surface
misconfigurations that still boot.
"""

from __future__ import annotations

from django.core.checks import Error, Tags, Warning, register

_KNOWN_KEYS = frozenset({"host", "subdomain", "urlconf", "redirect_to"})


@register(Tags.urls)
def check_hostmap(app_configs, **kwargs):
    from hostmap.conf import hostmap_settings

    hostmap = hostmap_settings.MAP
    if not hostmap:
        return []  # empty map disables all behaviour; nothing to validate

    problems = []
    problems.extend(_check_entries(hostmap))
    problems.extend(_check_default(hostmap))
    problems.extend(_check_duplicate_hosts())
    problems.extend(_check_allowed_hosts())
    problems.extend(_check_middleware())
    problems.extend(_check_root_urlconf())
    problems.extend(_check_django_ceiling())
    return problems


def _check_entries(hostmap):
    from django.conf import settings

    problems = []
    parent_domain = getattr(settings, "HOSTMAP_PARENT_DOMAIN", "")
    labels = set(hostmap.keys())

    for label, entry in hostmap.items():
        # E001: malformed entry (not a dict, unknown keys).
        if not isinstance(entry, dict):
            problems.append(Error(f"HOSTMAP entry '{label}' is not a dict.", id="hostmap.E001"))
            continue
        unknown = set(entry) - _KNOWN_KEYS
        if unknown or not entry:
            problems.append(
                Error(
                    f"HOSTMAP entry '{label}' is empty or has unknown keys: {sorted(unknown)}.",
                    hint=f"Valid keys: {sorted(_KNOWN_KEYS)}.",
                    id="hostmap.E001",
                )
            )
            continue

        has_host = "host" in entry
        has_subdomain = "subdomain" in entry
        # E002: exactly one of host / subdomain.
        if has_host == has_subdomain:
            problems.append(
                Error(
                    f"HOSTMAP entry '{label}' must set exactly one of 'host' or 'subdomain'.",
                    id="hostmap.E002",
                )
            )

        has_urlconf = "urlconf" in entry
        has_redirect = "redirect_to" in entry
        # E003: exactly one of urlconf / redirect_to.
        if has_urlconf == has_redirect:
            problems.append(
                Error(
                    f"HOSTMAP entry '{label}' must set exactly one of 'urlconf' or 'redirect_to'.",
                    id="hostmap.E003",
                )
            )

        # E004: redirect_to must name a known, non-redirect label (no chains).
        if has_redirect:
            target = entry["redirect_to"]
            if target not in labels:
                problems.append(
                    Error(
                        f"HOSTMAP entry '{label}' redirects to unknown label '{target}'.",
                        id="hostmap.E004",
                    )
                )
            elif isinstance(hostmap.get(target), dict) and "redirect_to" in hostmap[target]:
                problems.append(
                    Error(
                        f"HOSTMAP entry '{label}' redirects to another redirect entry '{target}' (no chains).",
                        id="hostmap.E004",
                    )
                )

        # E006: unimportable URLconf.
        if has_urlconf:
            problems.extend(_check_urlconf_importable(label, entry["urlconf"]))

        # E008: subdomain entry without HOSTMAP_PARENT_DOMAIN.
        if has_subdomain and not parent_domain:
            problems.append(
                Error(
                    f"HOSTMAP entry '{label}' uses 'subdomain' but HOSTMAP_PARENT_DOMAIN is not set.",
                    id="hostmap.E008",
                )
            )

    return problems


def _check_urlconf_importable(label, urlconf):
    from importlib import import_module

    try:
        import_module(urlconf)
    except Exception as exc:  # noqa: BLE001 - report any import failure
        return [
            Error(
                f"HOSTMAP entry '{label}' URLconf '{urlconf}' is not importable: {exc}.",
                id="hostmap.E006",
            )
        ]
    return []


def _check_default(hostmap):
    # E005: HOSTMAP_DEFAULT missing or not a map label while the map is non-empty.
    from django.conf import settings

    default = getattr(settings, "HOSTMAP_DEFAULT", "")
    if not default or default not in hostmap:
        return [
            Error(
                f"HOSTMAP_DEFAULT ('{default}') is missing or not a HOSTMAP label.",
                hint="Set HOSTMAP_DEFAULT to one of the map's labels.",
                id="hostmap.E005",
            )
        ]
    return []


def _check_duplicate_hosts():
    # E007: duplicate effective hosts.
    from hostmap.map import resolved_entries

    seen = {}
    problems = []
    for entry in resolved_entries().values():
        if entry.host in seen:
            problems.append(
                Error(
                    f"HOSTMAP entries '{seen[entry.host]}' and '{entry.label}' resolve to the same host '{entry.host}'.",
                    id="hostmap.E007",
                )
            )
        else:
            seen[entry.host] = entry.label
    return problems


def _check_allowed_hosts():
    # W001: mapped host not covered by ALLOWED_HOSTS.
    from django.conf import settings

    from hostmap.map import resolved_entries

    allowed = settings.ALLOWED_HOSTS
    if "*" in allowed:
        return []

    problems = []
    for entry in resolved_entries().values():
        if entry.wildcard:
            continue  # wildcard coverage is a leading-dot ALLOWED_HOSTS concern
        if not _host_allowed(entry.host, allowed):
            problems.append(
                Warning(
                    f"HOSTMAP host '{entry.host}' (entry '{entry.label}') is not covered by ALLOWED_HOSTS.",
                    id="hostmap.W001",
                )
            )
    return problems


def _host_allowed(host, allowed):
    for pattern in allowed:
        if pattern == host:
            return True
        if pattern.startswith(".") and (host == pattern[1:] or host.endswith(pattern)):
            return True
    return False


def _check_middleware():
    # W002: HOSTMAP configured without HostmapMiddleware installed.
    from django.conf import settings

    middleware = settings.MIDDLEWARE
    if not any(
        m.endswith("hostmap.middleware.HostmapMiddleware") or m == "hostmap.middleware.HostmapMiddleware"
        for m in middleware
    ):
        return [
            Warning(
                "HOSTMAP is configured but HostmapMiddleware is not in MIDDLEWARE.",
                hint="Add 'hostmap.middleware.HostmapMiddleware' before CommonMiddleware.",
                id="hostmap.W002",
            )
        ]
    return []


def _check_root_urlconf():
    # W003: ROOT_URLCONF does not match the default entry's URLconf.
    from django.conf import settings

    from hostmap.map import default_entry

    entry = default_entry()
    if entry is None or entry.is_redirect:
        return []
    root = getattr(settings, "ROOT_URLCONF", None)
    if root != entry.urlconf:
        return [
            Warning(
                f"ROOT_URLCONF ('{root}') does not match the default entry's URLconf ('{entry.urlconf}').",
                hint="Point ROOT_URLCONF at the HOSTMAP_DEFAULT entry's URLconf.",
                id="hostmap.W003",
            )
        ]
    return []


def _check_django_ceiling():
    # W004: running Django is newer than the package's tested ceiling.
    import django

    from hostmap.apps import TESTED_DJANGO_CEILING

    if django.VERSION[:2] > TESTED_DJANGO_CEILING:
        ceiling = ".".join(str(n) for n in TESTED_DJANGO_CEILING)
        running = ".".join(str(n) for n in django.VERSION[:2])
        return [
            Warning(
                f"Running Django {running} is newer than django-hostmap's tested ceiling ({ceiling}).",
                hint="If reversing misbehaves, set HOSTMAP_PATCH_REVERSE = False until a compatible release ships.",
                id="hostmap.W004",
            )
        ]
    return []
