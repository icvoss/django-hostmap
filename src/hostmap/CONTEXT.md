# hostmap package context

Build-session orientation for `src/hostmap/`. The authoritative spec is
`docs/specs/django-hostmap/` in the oss umbrella (APP-026); this file is the
in-tree map from spec to code.

## What this package does

Routes requests to per-host URLconfs and makes URL reversing host-aware
without any call-site changes: stock `reverse()` / `reverse_lazy()` /
`{% url %}` stay working everywhere, same-host links relative, cross-host
links absolute. No models, no migrations, no templates, no API layer.

## Module map

| Module | Role | Key rules |
|--------|------|-----------|
| `conf.py` | `HOSTMAP_*` settings with defaults, read lazily via `hostmap_settings` | 04-interfaces s2 |
| `map.py` | Parse `HOSTMAP` into cached `ResolvedEntry` objects; host matching; wildcard capture | BR-001, 002, 005 |
| `context.py` | Active-entry contextvar; also syncs Django's `set_urlconf()` so same-host reverse is native | BR-003, 006; AC-016 |
| `middleware.py` | `HostmapMiddleware`: route, set `request.urlconf`, `request.hostmap`, redirects | BR-001, 002, 008, 009 |
| `urls.py` | The single resolution code path (`_resolve`) + explicit API (`reverse`, `build_absolute_uri`, `use_host`) | BR-004, 005, 006 |
| `resolvers.py` | The seam: wraps `get_resolver` so the active URLconf gets `HostAwareResolver`, adding cross-host fallback under stock `reverse()` | 03-services s2; BR-004, 007 |
| `apps.py` | Install the seam at `ready()`, run the self-test, register checks | BR-007; seam guards |
| `checks.py` | System checks E001-E008, W001-W004 | 04-interfaces s3 |
| `management/commands/hostmap.py` | `manage.py hostmap` diagnostic | 04-interfaces s4 |
| `testing/` | `host_client()`, pytest fixtures, `use_host` re-export | 04-interfaces s6 |

## Two design constraints to preserve

1. **One resolution code path** (watch flag 2). `hostmap.urls._resolve()` is
   the only host-aware resolution logic. The seam's
   `HostAwareResolver._cross_host_reverse` and the explicit API both walk the
   same BR-005 order and call the same `_absolute_url`. Never grow a second
   implementation.
2. **Fallback resolvers must stay plain.** Only the *active* URLconf is ever
   wrapped in `HostAwareResolver`; `resolvers._stock_resolver` deliberately
   uses the original `get_resolver` so the hosts we fall back to are ordinary
   resolvers. Wrapping them would recurse. The first build hit exactly this
   bug; do not re-introduce it by "simplifying" the wrapper.

## The seam, precisely

`django.urls.base.reverse(urlconf=None)` resolves `urlconf` via
`get_urlconf()` (which `context.set_active` keeps pointed at the active
entry), then calls `get_resolver(urlconf)._reverse_with_prefix(...)`. We
replace `get_resolver` in both `django.urls.resolvers` and `django.urls.base`
(the latter early-binds it). For the active URLconf we return a cached
`HostAwareResolver`; on a same-host `NoReverseMatch` it walks the other
entries and returns an absolute URL. Same-host success never enters the
fallback, so BR-003 is byte-identical for free.

## Testing

pytest + pytest-django, SQLite, `DJANGO_SETTINGS_MODULE=settings`,
`PYTHONPATH=src:tests`. The comparison suite (`tests/test_comparison.py`,
AC-001/002/003) is the real release gate. `tests/thirdparty_app` binds
`reverse`/`reverse_lazy` at import time, before `hostmap.ready()`, to prove
the seam reaches early-bound references.
