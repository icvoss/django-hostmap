# Troubleshooting

Symptom-first reference for django-hostmap. Find your symptom, read the
likely cause, apply the fix. For the exhaustive settings and system check
tables, see the [settings reference](reference/settings.md).

---

## Quick lookup

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Requests behind nginx (or another proxy) go to the wrong host, or always to the default | The proxy is not forwarding the original `Host` header | See [misrouted hosts behind a proxy](#misrouted-hosts-behind-a-proxy) below |
| `hostmap.W003` at startup | `ROOT_URLCONF` does not match the default entry's `urlconf` | Point `ROOT_URLCONF` at the same module as `HOSTMAP_DEFAULT`'s entry |
| A host past `ALLOWED_HOSTS` serves the default entry, not `Http404` | `HOSTMAP_UNMATCHED` is `"default"` (the default setting), and this is deliberate | Set `HOSTMAP_UNMATCHED = "reject"` if you want a hard 404 instead |
| `NoReverseMatch` naming several hosts | The URL name genuinely does not exist on any mapped host's URLconf | Confirm the name and check `manage.py hostmap` for the map you expect |
| A Django upgrade breaks reversing, or startup fails with `ImproperlyConfigured` naming hostmap | The resolver-acquisition seam does not hold on the new Django version | Set `HOSTMAP_PATCH_REVERSE = False` until a compatible release ships |
| `hostmap.W004` at startup | Running Django is newer than the package's tested ceiling | Advance warning, not an error; test the upgrade in a branch before trusting reversing in production |
| `hostmap.E001` | A `HOSTMAP` entry is not a dict, is empty, or has unknown keys | Fix the entry's keys; valid keys are `host`, `subdomain`, `urlconf`, `redirect_to` |
| `hostmap.E002` | An entry sets both `host` and `subdomain`, or neither | Set exactly one |
| `hostmap.E003` | An entry sets both `urlconf` and `redirect_to`, or neither | Set exactly one |
| `hostmap.E004` | `redirect_to` names an unknown label, or another redirect entry | Point `redirect_to` at a real, non-redirect label |
| `hostmap.E005` | `HOSTMAP_DEFAULT` missing or not a map label | Set `HOSTMAP_DEFAULT` to one of the map's labels |
| `hostmap.E006` | An entry's `urlconf` cannot be imported | Fix the dotted path or the module's own import errors |
| `hostmap.E007` | Two entries resolve to the same effective host | Rename or remove the duplicate |
| `hostmap.E008` | A `subdomain` entry exists but `HOSTMAP_PARENT_DOMAIN` is unset | Set `HOSTMAP_PARENT_DOMAIN` |
| `hostmap.W001` | A mapped host is not covered by `ALLOWED_HOSTS` | Add the host to `ALLOWED_HOSTS` |
| `hostmap.W002` | `HOSTMAP` is configured but `HostmapMiddleware` is not installed | Add `hostmap.middleware.HostmapMiddleware` to `MIDDLEWARE`, before `CommonMiddleware` |

---

## Misrouted hosts behind a proxy

**Triggers when:** the deployment sits behind nginx, a load balancer, or a
CDN, and requests are routed to the wrong host, or consistently land on the
`HOSTMAP_DEFAULT` entry regardless of the hostname a client actually
requested.

**Cause:** `HostmapMiddleware` matches on `request.get_host()`, which reads
the `Host` header (or `X-Forwarded-Host`, if `USE_X_FORWARDED_HOST` is set).
If the proxy rewrites, drops, or does not forward the original header,
Django never sees the hostname the client requested, and every request
looks identical from hostmap's point of view.

**Fix:** confirm the proxy forwards the original `Host` header unchanged
(`proxy_set_header Host $host;` for nginx), or set
`USE_X_FORWARDED_HOST = True` if the proxy instead sets
`X-Forwarded-Host`, only once you have verified the proxy is the sole entry
point. This is the single most common support issue for any host-based
routing package; see [run behind a proxy](how-to/run-behind-a-proxy.md) for
the full walkthrough.

---

## `NoReverseMatch` naming hosts

**Triggers when:** `reverse()`, `{% url %}`, or `hostmap.urls.reverse()`
finds the name on no entry in the search order (active host, default entry,
then declaration order).

The message names every host that was searched:

```
NoReverseMatch: Reverse for 'nonexistent-view' not found on any hostmap
host. Searched: www.example.com, api.example.com.
```

**Fix:** confirm the name is spelled correctly and actually exists in one of
the listed URLconfs. Run `manage.py hostmap` to see exactly which URLconf
each host resolves to, then check that URLconf directly for the name. If the
name only exists on a wildcard entry, remember wildcards are excluded from
this search; use `use_host(host=...)` instead (see
[use wildcard subdomains](how-to/use-wildcard-subdomains.md)).

Inside a template, `{% url ... as var %}` keeps Django's silent-failure
contract: no exception, `var` simply stays unassigned.

---

## Django-upgrade seam breakage

**Triggers when:** a Django upgrade changes internals the resolver
acquisition seam depends on. Two distinct symptoms:

1. **Startup fails with `ImproperlyConfigured`**, naming the remediation
   directly: this is the `AppConfig.ready()` self-test catching a broken
   seam before any production traffic hits it.
2. **`hostmap.W004` warns at startup**, even though the self-test passed:
   this is advance notice that the running Django is newer than the
   package's tested ceiling, not proof that anything is currently broken.

**Fix:** set `HOSTMAP_PATCH_REVERSE = False`. Routing keeps working
unchanged; cross-host links from stock `reverse()` regress to raising
`NoReverseMatch` (the same as if hostmap were not installed at all), and the
explicit API (`hostmap.urls.reverse`, `build_absolute_uri`, `use_host`)
keeps working, since it calls the same resolution logic independently of the
patch. See [turn off reversing](how-to/turn-off-reversing.md). Watch for a
django-hostmap release declaring support for the new Django version, then
re-enable the patch.

---

## System checks

### `hostmap.E001`: malformed entry

**Triggers when:** an entry is not a dict, is empty, or has a key outside
`{"host", "subdomain", "urlconf", "redirect_to"}`.

**Fix:**

```python
HOSTMAP = {
    "api": {"subdomain": "api", "urlconf": "config.urls.api"},  # valid keys only
}
```

### `hostmap.E002`: both or neither of `host` / `subdomain`

**Fix:** set exactly one per entry. Use `subdomain` for a label joined to
`HOSTMAP_PARENT_DOMAIN`; use `host` for a full, independent domain.

### `hostmap.E003`: both or neither of `urlconf` / `redirect_to`

**Fix:** a routing entry sets `urlconf`; a redirect entry sets
`redirect_to`. Never both, never neither.

### `hostmap.E004`: bad redirect target

**Triggers when:** `redirect_to` names a label that does not exist, or
names another redirect entry (chains are rejected outright).

**Fix:** point `redirect_to` directly at the real, non-redirect destination
label.

### `hostmap.E005`: missing or invalid default

**Fix:**

```python
HOSTMAP_DEFAULT = "www"  # must be a key in HOSTMAP
```

### `hostmap.E006`: unimportable URLconf

**Triggers when:** an entry's `urlconf` value raises on import.

**Fix:** the check message includes the underlying import error; fix the
dotted path or whatever is failing inside that module.

### `hostmap.E007`: duplicate effective hosts

**Triggers when:** two entries resolve to the same host (for example, a
`subdomain: "www"` entry and a `host: "www.example.com"` entry under the
same parent domain).

**Fix:** rename or remove one of the colliding entries.

### `hostmap.E008`: subdomain entry with no parent domain

**Fix:**

```python
HOSTMAP_PARENT_DOMAIN = "example.com"
```

### `hostmap.W001`: mapped host outside `ALLOWED_HOSTS`

**Triggers when:** a non-wildcard entry's host is not covered by
`ALLOWED_HOSTS` (wildcard coverage is a leading-dot `ALLOWED_HOSTS` concern
and is not checked here).

**Fix:**

```python
ALLOWED_HOSTS = ["www.example.com", "api.example.com"]
```

### `hostmap.W002`: middleware not installed

**Fix:** add it before `CommonMiddleware`:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "hostmap.middleware.HostmapMiddleware",
    "django.middleware.common.CommonMiddleware",
    # ...
]
```

### `hostmap.W003`: `ROOT_URLCONF` mismatch

**Triggers when:** `ROOT_URLCONF` does not equal the default entry's
`urlconf`.

**Fix:** point `ROOT_URLCONF` at the same module the default entry uses;
Django needs `ROOT_URLCONF` at startup regardless of hostmap, and keeping
the two in sync avoids surprising behaviour for anything that reads
`ROOT_URLCONF` directly.

### `hostmap.W004`: Django version ceiling

See [Django-upgrade seam breakage](#django-upgrade-seam-breakage) above.

---

## Common gotchas

### An unmapped host serves the default entry

**Cause:** `HOSTMAP_UNMATCHED` defaults to `"default"`. Any host that
passes `ALLOWED_HOSTS` but matches no `HOSTMAP` entry is deliberately served
by the default entry rather than rejected, so a typo'd or unexpected host
still gets a response.

**Fix:** this may be exactly what you want. If not, set
`HOSTMAP_UNMATCHED = "reject"` for a hard `Http404` instead.

### `request.hostmap` is missing

**Cause:** either `HOSTMAP` is empty (hostmap is a full pass-through, by
design), or the request went through `RequestFactory` rather than a real
`Client`, so `HostmapMiddleware` never ran.

**Fix:** confirm `HOSTMAP` has entries, and use
[`host_client()`](how-to/test-host-routing.md) in tests rather than
`RequestFactory` when you need routing to actually run.

### A wildcard subdomain will not reverse

**Cause:** wildcard entries have no single concrete host, so they are
excluded from the cross-host fallback search entirely.

**Fix:** use `use_host(host="concrete.example.com")` to pin the specific
subdomain explicitly. See
[use wildcard subdomains](how-to/use-wildcard-subdomains.md).

---

## Related

- [Settings reference](reference/settings.md): full settings and system
  check tables.
- [How host-aware reversing works](explanation/how-host-aware-reversing-works.md):
  the resolver seam and the runtime guards referenced above.
- [Resolution order](explanation/resolution-order.md): the exact search
  order behind `NoReverseMatch` messages.
