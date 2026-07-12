# django-hostmap documentation

Host-based URL routing and host-aware reversing for Django, with zero
call-site changes.

These guides are task-focused. For the exhaustive settings and system check
tables, see the [settings reference](reference/settings.md); for the explicit
API and testing helpers, see the [API reference](reference/api.md).

## The two-line install

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

Then declare one host map:

```python
HOSTMAP = {
    "www": {"subdomain": "www", "urlconf": "config.urls.www"},
    "api": {"subdomain": "api", "urlconf": "config.urls.api"},
    "apex": {"host": "example.com", "redirect_to": "www"},
}
HOSTMAP_PARENT_DOMAIN = "example.com"
HOSTMAP_DEFAULT = "www"
```

`ROOT_URLCONF` still points at your default host's URLconf, exactly as Django
requires.

## The promise

With `www` active, nothing at the call site changes:

| Call | Returns |
|------|---------|
| `reverse("blog:index")` | `/blog/` (byte-identical to stock Django) |
| `reverse("api:user-detail", args=[7])` | `https://api.example.com/users/7/` |
| `{% url "api:user-detail" 7 %}` | the absolute URL, no template changes |

**Same-host links stay relative. Cross-host links come back absolute.** The
stock `reverse()`, `reverse_lazy()` and `{% url %}` do this everywhere,
including inside third-party apps you never touch, because hostmap hooks
resolver acquisition rather than patching `reverse` itself. See
[how host-aware reversing works](explanation/how-host-aware-reversing-works.md)
for why that distinction matters.

## I want to...

| I want to... | Go to |
| --- | --- |
| Build a two-host project from scratch | [Multi-host in ten minutes](tutorial/multi-host-in-ten-minutes.md) |
| Route a subdomain to its own URLconf | [Route a subdomain to its own URLconf](how-to/route-a-subdomain-to-its-own-urlconf.md) |
| Understand `{% url %}` and `reverse()` behaviour | [Link across hosts in templates and Python](how-to/link-across-hosts-in-templates-and-python.md) |
| Reverse a URL from a Celery task, email, or webhook | [Reverse out of a request](how-to/reverse-out-of-a-request.md) |
| Redirect the apex domain to `www` | [Add a redirect host](how-to/add-a-redirect-host.md) |
| Route arbitrary subdomains (multi-tenant style) | [Use wildcard subdomains](how-to/use-wildcard-subdomains.md) |
| Move off django-hosts | [Migrate from django-hosts](how-to/migrate-from-django-hosts.md) |
| Write tests that hit the right host | [Test host routing](how-to/test-host-routing.md) |
| Deploy behind nginx or another reverse proxy | [Run behind a proxy](how-to/run-behind-a-proxy.md) |
| Disable the reverse patch and keep routing only | [Turn off reversing](how-to/turn-off-reversing.md) |
| Understand the resolver-acquisition seam | [How host-aware reversing works](explanation/how-host-aware-reversing-works.md) |
| Understand cross-host resolution order | [Resolution order](explanation/resolution-order.md) |
| Look up a `HOSTMAP_*` setting | [Settings reference](reference/settings.md) |
| Look up `hostmap.urls` or `hostmap.testing` | [API reference](reference/api.md) |
| Fix an error or unexpected behaviour | [Troubleshooting](troubleshooting.md) |

## How these docs are organised

The documentation follows the [Diátaxis](https://diataxis.fr/) model:

- **[Tutorial](tutorial/multi-host-in-ten-minutes.md)**: a single, opinionated
  path from nothing to a working two-host project. Start here if you are new.
- **How-to guides**: recipes for specific tasks. Each one states a goal,
  lists prerequisites, gives runnable steps, and shows how to verify the
  result.
- **Explanation**: the "why": the resolver-acquisition seam, why same-host
  reversing is free, and the fixed cross-host resolution order. Read these to
  build a mental model.
- **[Settings reference](reference/settings.md)** and
  **[API reference](reference/api.md)**: the exhaustive lookup tables.
- **[Troubleshooting](troubleshooting.md)**: symptom, cause, fix.

## New to django-hostmap?

1. Follow the [tutorial](tutorial/multi-host-in-ten-minutes.md) end to end.
2. Read
   [how host-aware reversing works](explanation/how-host-aware-reversing-works.md)
   to understand why the package can fix third-party apps' `reverse()` calls
   without changing them.
3. Keep the [settings reference](reference/settings.md) and
   [troubleshooting](troubleshooting.md) page open as you integrate, and read
   [run behind a proxy](how-to/run-behind-a-proxy.md) before you deploy: a
   misrouted Host header is the most common support issue.
