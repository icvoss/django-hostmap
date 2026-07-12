# django-hostmap

Host-based URL routing and host-aware reversing for Django, with zero
call-site changes.

`django-hostmap` routes requests to different URLconfs by host (subdomain or
full domain) and makes URL reversing host-aware without changing a single
call site: the stock `reverse()`, `reverse_lazy()` and `{% url %}` keep
working everywhere, including inside third-party apps. Links within the
current host stay path-relative, exactly as Django produces them; links to
views on another host come back as absolute URLs. Configuration is one
declarative host map in settings plus one middleware.

It is the ecosystem's replacement for django-hosts, whose parallel reverse
API forces invasive changes across templates and Python code and cannot fix
third-party apps that call `django.urls.reverse()`.

## Installation

```bash
pip install django-hostmap
```

```python
INSTALLED_APPS = [
    # ...
    "hostmap",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "hostmap.middleware.HostmapMiddleware",  # before CommonMiddleware
    "django.middleware.common.CommonMiddleware",
    # ...
]
```

`ROOT_URLCONF` remains required (Django needs it at startup) and should point
at the default entry's URLconf (`hostmap.W003` warns on mismatch).

## The host map

```python
HOSTMAP = {
    "www": {"subdomain": "www", "urlconf": "config.urls.www"},
    "api": {"subdomain": "api", "urlconf": "config.urls.api"},
    "apex": {"host": "example.com", "redirect_to": "www"},
}
HOSTMAP_PARENT_DOMAIN = "example.com"
HOSTMAP_DEFAULT = "www"
```

With `www` active:

| Call | Returns |
|------|---------|
| `reverse("blog:index")` | `/blog/` (byte-identical to stock Django) |
| `reverse("api:user-detail", args=[7])` | `https://api.example.com/users/7/` |
| `{% url "api:user-detail" 7 %}` | the absolute URL, no template changes |

Same-host links stay relative; cross-host links come back absolute. Nothing
at the call site changes.

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `HOSTMAP` | `{}` | The host map. Empty map disables all behaviour |
| `HOSTMAP_PARENT_DOMAIN` | `""` | Domain joined to `subdomain` entries |
| `HOSTMAP_DEFAULT` | `""` | Entry for unmatched hosts and out-of-request reversing |
| `HOSTMAP_PATCH_REVERSE` | `True` | Make stock `reverse()` / `{% url %}` host-aware |
| `HOSTMAP_SCHEME` | `"https"` | Scheme for cross-host absolute URLs |
| `HOSTMAP_PORT` | `""` | Port appended to all generated hosts |
| `HOSTMAP_UNMATCHED` | `"default"` | `"default"` routes unmatched hosts to the default entry; `"reject"` returns 404 |
| `HOSTMAP_REDIRECT_PERMANENT` | `True` | `redirect_to` entries use 301, else 302 |

## Explicit API

For code that needs an absolute URL regardless of the active host (emails,
Celery tasks, API payloads, webhooks):

```python
from hostmap.urls import reverse, build_absolute_uri, use_host

build_absolute_uri("api:user-detail", args=[7])          # always absolute
with use_host("api"):
    reverse("user-detail", args=[7])                     # api active

with use_host(host="acme.example.com"):                  # a wildcard host
    reverse("dashboard")
```

## Development story

Modern browsers resolve `*.localhost` to loopback (RFC 6761), so the whole
map works locally with no `/etc/hosts` edits:

```python
HOSTMAP_PARENT_DOMAIN = "localhost"
HOSTMAP_SCHEME = "http"
HOSTMAP_PORT = "8000"
ALLOWED_HOSTS = [".localhost"]
```

## Behind a proxy

Host routing is only as good as the Host header that reaches Django. Behind a
reverse proxy, either the proxy passes Host through unchanged or the
deployment sets `USE_X_FORWARDED_HOST = True` with the proxy sending
`X-Forwarded-Host`. Misrouted hosts behind nginx are otherwise the first
support issue.

## Escape hatch

`HOSTMAP_PATCH_REVERSE = False` degrades cleanly to routing-only: the stock
`reverse()` is left untouched (cross-host links regress to paths), routing
keeps working, and the explicit API still works. Set it if a Django upgrade
lands before a compatible django-hostmap release; the startup self-test and
`hostmap.W004` warn before anything breaks.

## Diagnostics

```bash
manage.py hostmap    # print the resolved map for the current settings
```

## Licence

MIT. See [LICENSE](LICENSE).
