# Changelog

All notable changes to django-hostmap are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-12

Initial release. Host-based URL routing and host-aware reversing for Django,
built to the APP-026 specification (`docs/specs/django-hostmap/`).

### Added

- **Host routing** (`HostmapMiddleware`). Matches `request.get_host()` against
  a declarative `HOSTMAP`, sets `request.urlconf` per host, records the active
  entry in an async-safe contextvar, and populates the namespaced
  `request.hostmap` (`.label`, `.subdomain`). Case-insensitive, port-blind
  (BR-HOSTMAP-001, 002).
- **Host-aware reversing** through the stock `reverse()`, `reverse_lazy()` and
  `{% url %}`, with zero call-site changes. Same-host links stay byte-identical
  to stock Django (BR-HOSTMAP-003); cross-host links come back absolute
  (BR-HOSTMAP-004). The resolver-acquisition seam makes even third-party apps'
  early-bound `reverse` imports host-aware.
- **Fixed resolution order**: active host, default entry, then declaration
  order; `NoReverseMatch` (naming the searched hosts) when a name resolves
  nowhere; per-host resolvers cached (BR-HOSTMAP-005).
- **Redirect entries** (`redirect_to`): answer every path on their host with a
  path- and query-preserving redirect, 301 by default (BR-HOSTMAP-008).
- **Wildcard subdomain entries** (`subdomain: "*"`): route and capture the
  subdomain onto `request.hostmap.subdomain` (BR-HOSTMAP-009).
- **Explicit API** (`hostmap.urls`): `reverse()`, `build_absolute_uri()` and
  the `use_host()` context manager for absolute URLs out of a request (emails,
  Celery tasks, webhooks). One resolution code path shared with the patch.
- **Escape hatch** `HOSTMAP_PATCH_REVERSE = False`: degrades cleanly to
  routing-only, leaving Django's reversing untouched (BR-HOSTMAP-007).
- **Runtime seam guards**: a `ready()`-time self-test fails startup with
  `ImproperlyConfigured` if Django's reverse seam has moved; the
  `hostmap.W004` system check warns on a Django newer than the tested ceiling.
- **System checks** `hostmap.E001`-`E008` and `hostmap.W001`-`W004` validating
  the map and its integration at startup.
- **`manage.py hostmap`**: print the resolved map for the current settings.
- **Testing helpers** (`hostmap.testing`): `host_client(label)`, pytest
  fixtures, and a `use_host` re-export.

[0.1.0]: https://github.com/icvoss/django-hostmap/releases/tag/v0.1.0
