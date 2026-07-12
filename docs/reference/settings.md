# Settings reference

django-hostmap is configured entirely through Django's `settings.py`. All
settings use the `HOSTMAP_` prefix (with the exception of `HOSTMAP` itself,
the map dict) and are read lazily via `hostmap_settings`, so they can be
overridden in test suites without a process restart. There is no required
setting: an empty or unset `HOSTMAP` disables all hostmap behaviour and the
package is a transparent pass-through.

---

## `HOSTMAP`

| | |
|---|---|
| **Type** | `dict` |
| **Default** | `{}` |

The host map. Keys are stable labels used in code (`use_host("api")`) and
diagnostics; values are entry dicts. Declaration order is significant for
cross-host resolution (see
[resolution order](../explanation/resolution-order.md)).

```python
HOSTMAP = {
    "www": {"subdomain": "www", "urlconf": "config.urls.www"},
    "api": {"subdomain": "api", "urlconf": "config.urls.api"},
    "apex": {"host": "example.com", "redirect_to": "www"},
}
```

Each entry sets exactly one of `host` / `subdomain`, and exactly one of
`urlconf` / `redirect_to`:

| Key | Type | Meaning |
|-----|------|---------|
| `host` | str | Full host, e.g. `"app.example.co.uk"`. Mutually exclusive with `subdomain` |
| `subdomain` | str | Label joined to `HOSTMAP_PARENT_DOMAIN`. `""` means the parent domain itself; `"*"` matches any single-level subdomain |
| `urlconf` | str | Dotted path to this host's URLconf. Mutually exclusive with `redirect_to` |
| `redirect_to` | str | Label of a non-redirect entry; requests to this host redirect there, preserving path and query string |

**When to change it:** Set once at project setup, then add an entry per host
as your project grows. An empty map (the default) makes
`HostmapMiddleware` a transparent pass-through: no routing, no
`request.hostmap`, no active-host context, and the reverse patch is never
installed. This is what makes it safe to install the middleware
unconditionally in a shared settings base, with the map itself configured
per environment.

**System checks:** `hostmap.E001` through `hostmap.E008` all validate this
setting's structure; see the [system checks](#system-checks) table below.

---

## `HOSTMAP_PARENT_DOMAIN`

| | |
|---|---|
| **Type** | `str` |
| **Default** | `""` |

Domain joined to `subdomain` entries to form their effective host.

**When to change it:** Set to your production domain
(`HOSTMAP_PARENT_DOMAIN = "example.com"`), overridden to `"localhost"` in
development so `*.localhost` resolves to loopback with no `/etc/hosts`
edits (see the [tutorial](../tutorial/multi-host-in-ten-minutes.md)).

**Interactions:** Required whenever any entry uses `subdomain`
(`hostmap.E008` fires if it is missing on such an entry). Not needed for
maps that only use `host` entries.

---

## `HOSTMAP_DEFAULT`

| | |
|---|---|
| **Type** | `str` |
| **Default** | `""` |

The entry label used for unmatched hosts (when `HOSTMAP_UNMATCHED` is
`"default"`) and for out-of-request reversing (Celery tasks, management
commands, shell, import-time `reverse_lazy`).

**When to change it:** Required whenever `HOSTMAP` is non-empty
(`hostmap.E005` fires if it is missing or not a map label). Point it at
whichever entry should also be your `ROOT_URLCONF`
(`hostmap.W003` warns on mismatch).

**Interactions:** Read by `hostmap.context.get_active()` whenever no active
entry is set: outside a request, the contextvar is unset, so callers fall
back to this entry. See
[resolution order](../explanation/resolution-order.md).

---

## `HOSTMAP_PATCH_REVERSE`

| | |
|---|---|
| **Type** | `bool` |
| **Default** | `True` |

Makes stock `reverse()`, `reverse_lazy()` and `{% url %}` host-aware by
installing the resolver-acquisition seam at `AppConfig.ready()`. When
`False`, Django's reversing is left completely untouched; routing still
works, and the explicit API (`hostmap.urls.reverse`, `build_absolute_uri`,
`use_host`) still works, since it calls the same resolution logic
independently of the patch.

**When to change it:** Set to `False` as an escape hatch if a Django
upgrade lands before a compatible django-hostmap release, or as a
deliberate, permanent choice if you only want host-based routing and are
willing to use the explicit API everywhere you need a cross-host URL. See
[turn off reversing](../how-to/turn-off-reversing.md).

**Trade-off:** With the patch off, a cross-host URL name reversed through
stock `reverse()` raises `NoReverseMatch` rather than returning an absolute
URL, the same as it would with no hostmap installed at all.

**Read once at startup:** the setting is consulted at `AppConfig.ready()`
to decide whether to install the seam; flipping it via a live `settings`
override does not retroactively install or remove the patch mid-process.

**Related check:** `hostmap.W004` (see below) fires independently of this
setting, warning about the Django version ceiling regardless of whether the
patch is installed.

---

## `HOSTMAP_SCHEME`

| | |
|---|---|
| **Type** | `str` |
| **Default** | `"https"` |

Scheme used when composing cross-host absolute URLs
(`scheme://host[:port]/path`).

**When to change it:** Override to `"http"` in local development, where
TLS is not in play. Production should keep the default.

**Interactions:** Applies uniformly across every cross-host URL; there is
no per-entry scheme override. Protocol-relative URLs (`//host/path`) were
considered and cut: `HOSTMAP_SCHEME` already applies uniformly, so there is
no mixed-scheme problem for a protocol-relative form to solve.

---

## `HOSTMAP_PORT`

| | |
|---|---|
| **Type** | `str` |
| **Default** | `""` |

Port appended to every generated cross-host host (`host:port`). Empty means
no port is appended (the normal case in production, where the scheme's
default port applies).

**When to change it:** Set to your development server's port
(`"8000"`) so cross-host URLs generated locally are directly usable.

**Interactions:** One port applies uniformly to every entry; there is no
per-host port setting, since a single Django process serving multiple hosts
during development runs them all on the same port.

---

## `HOSTMAP_UNMATCHED`

| | |
|---|---|
| **Type** | `str` |
| **Default** | `"default"` |

Behaviour for a request whose host matches no `HOSTMAP` entry (but passed
`ALLOWED_HOSTS` validation, so Django itself accepted it).

| Value | Behaviour |
|-------|-----------|
| `"default"` | Serve the request using the `HOSTMAP_DEFAULT` entry |
| `"reject"` | Raise `Http404` |

**When to change it:** Set to `"reject"` for deployments where an
allowed-but-unmapped host should be rejected outright rather than
transparently served by the default entry. See
[run behind a proxy](../how-to/run-behind-a-proxy.md).

---

## `HOSTMAP_REDIRECT_PERMANENT`

| | |
|---|---|
| **Type** | `bool` |
| **Default** | `True` |

Whether `redirect_to` entries issue a 301 (permanent, cached by browsers and
search engines) or a 302 (temporary).

**When to change it:** Set to `False` while you are still deciding on a
final canonical host and do not want intermediate redirects cached.

**Interactions:** Applies to every redirect entry in the map; there is no
per-entry override. See [add a redirect host](../how-to/add-a-redirect-host.md).

---

## System checks

hostmap registers Django system checks, run at startup and during test
collection under `Tags.urls`. Errors (`E0xx`) fail startup; warnings
(`W0xx`) are advisory.

### Errors

| ID | Condition |
|----|-----------|
| `hostmap.E001` | Entry is not a dict, is empty, or has unknown keys |
| `hostmap.E002` | An entry sets both `host` and `subdomain`, or neither |
| `hostmap.E003` | An entry sets both `urlconf` and `redirect_to`, or neither |
| `hostmap.E004` | `redirect_to` names an unknown label, or another redirect entry (chained redirects are rejected) |
| `hostmap.E005` | `HOSTMAP_DEFAULT` is missing or not a map label, while `HOSTMAP` is non-empty |
| `hostmap.E006` | An entry's `urlconf` cannot be imported |
| `hostmap.E007` | Two or more entries resolve to the same effective host |
| `hostmap.E008` | A `subdomain` entry is declared with `HOSTMAP_PARENT_DOMAIN` unset |

### Warnings

| ID | Condition |
|----|-----------|
| `hostmap.W001` | A mapped host is not covered by `ALLOWED_HOSTS` |
| `hostmap.W002` | `HOSTMAP` is configured but `HostmapMiddleware` is not in `MIDDLEWARE` |
| `hostmap.W003` | `ROOT_URLCONF` does not match the default entry's URLconf |
| `hostmap.W004` | The running Django version is newer than the package's tested ceiling |

---

## Management commands

| Command | Purpose |
|---------|---------|
| `manage.py hostmap` | Print the resolved map: each entry's effective host, URLconf, and redirect target, for the current settings |

---

## Quick reference

| Setting | Default | Required |
|---|---|---|
| `HOSTMAP` | `{}` | No (empty disables hostmap entirely) |
| `HOSTMAP_PARENT_DOMAIN` | `""` | Only if any entry uses `subdomain` |
| `HOSTMAP_DEFAULT` | `""` | Yes, once `HOSTMAP` is non-empty |
| `HOSTMAP_PATCH_REVERSE` | `True` | No |
| `HOSTMAP_SCHEME` | `"https"` | No |
| `HOSTMAP_PORT` | `""` | No |
| `HOSTMAP_UNMATCHED` | `"default"` | No |
| `HOSTMAP_REDIRECT_PERMANENT` | `True` | No |
