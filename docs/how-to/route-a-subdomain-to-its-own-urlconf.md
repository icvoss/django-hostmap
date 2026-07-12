# Route a subdomain to its own URLconf

## Goal

Add a new host to `HOSTMAP` so requests to a given subdomain (or full domain)
are routed to their own URLconf.

## Prerequisites

- `hostmap.middleware.HostmapMiddleware` installed in `MIDDLEWARE`, before
  `CommonMiddleware`.
- `hostmap` in `INSTALLED_APPS`.

## Steps

### 1. Decide `subdomain` or `host`

Each `HOSTMAP` entry sets exactly one of `subdomain` or `host`
(`hostmap.E002` fails startup otherwise):

| Key | Use when | Example |
|-----|----------|---------|
| `subdomain` | The host is `<label>.<HOSTMAP_PARENT_DOMAIN>` | `"api"` joined to `example.com` gives `api.example.com` |
| `host` | The host is a full domain unrelated to the parent domain, or the bare parent domain itself | `"app.example.co.uk"`, or `"example.com"` for the apex |

A `subdomain` of `""` means the parent domain itself (equivalent to
`host: "<parent>"`); a `subdomain` of `"*"` is a wildcard, covered in
[use wildcard subdomains](use-wildcard-subdomains.md).

### 2. Add the entry

```python
# settings.py
HOSTMAP = {
    "www": {"subdomain": "www", "urlconf": "config.urls.www"},
    "api": {"subdomain": "api", "urlconf": "config.urls.api"},
    "shop": {"host": "shop.example.co.uk", "urlconf": "config.urls.shop"},
}
HOSTMAP_PARENT_DOMAIN = "example.com"
HOSTMAP_DEFAULT = "www"
```

`shop` above is a `host` entry: it does not live under `HOSTMAP_PARENT_DOMAIN`
at all, so `subdomain` would not express it.

### 3. Point the entry at a real, importable URLconf

Each entry's `urlconf` is a dotted module path, exactly like `ROOT_URLCONF`.
It must be a plain Python module containing `urlpatterns`; hostmap does not
require anything special of it.

```python
# config/urls/shop.py
from django.urls import path

from shop import views

urlpatterns = [
    path("", views.storefront, name="storefront"),
]
```

An unimportable `urlconf` value fails startup as `hostmap.E006`, naming the
import error.

### 4. Confirm `ALLOWED_HOSTS` and `ROOT_URLCONF`

`ALLOWED_HOSTS` must cover every mapped host, or Django rejects the request
before hostmap ever sees it (`hostmap.W001` warns, but does not fail startup,
if a host is missing).

```python
ALLOWED_HOSTS = ["www.example.com", "api.example.com", "shop.example.co.uk"]
```

`ROOT_URLCONF` should point at the default entry's URLconf
(`hostmap.W003` warns otherwise), since Django needs `ROOT_URLCONF` at
startup regardless of hostmap.

## Verify it worked

```bash
python manage.py check
python manage.py hostmap
```

`manage.py check` should report no `hostmap.E0xx` errors. `manage.py hostmap`
should list the new entry with its resolved host and URLconf:

```
shop
    host:     shop.example.co.uk
    urlconf:  config.urls.shop
```

Then hit it directly:

```bash
curl -H "Host: shop.example.co.uk" http://localhost:8000/
```

## Common pitfalls

- **Setting both `host` and `subdomain`, or neither.** `hostmap.E002` fails
  startup either way; an entry is one or the other.
- **Forgetting `HOSTMAP_PARENT_DOMAIN`.** A `subdomain` entry with no parent
  domain configured fails as `hostmap.E008`.
- **Two entries resolving to the same effective host.** `hostmap.E007` fails
  startup; each entry's host must be unique.
- **`ALLOWED_HOSTS` missing the new host.** Django's own host validation
  rejects the request with a 400 before `HostmapMiddleware` runs at all; this
  is Django behaviour, not hostmap's, so it shows up as a 400, not a
  `Http404`.

## Related

- [Use wildcard subdomains](use-wildcard-subdomains.md): for `subdomain: "*"`
  entries that match any single-level subdomain.
- [Add a redirect host](add-a-redirect-host.md): for entries that redirect
  rather than route.
- [Settings reference](../reference/settings.md): the full `HOSTMAP_*` table
  and every system check.
