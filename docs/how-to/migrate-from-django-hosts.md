# Migrate from django-hosts

## Goal

Move a project from django-hosts to django-hostmap. The migration is
mechanical: translate `ROOT_HOSTCONF` entries into `HOSTMAP`, swap the
middleware, then delete `{% host_url %}` usages at your own pace, since
stock `{% url %}` now behaves correctly without them.

## Prerequisites

- The project currently uses django-hosts (`ROOT_HOSTCONF`,
  `hosts.middleware.HostsRequestMiddleware`, the `host_url` template tag, or
  `django_hosts.reverse()`).

## Steps

### 1. Translate `ROOT_HOSTCONF` into `HOSTMAP`

django-hosts declares hosts as a list of `(regex, urlconf, name)` patterns in
a separate `hosts.py` module. hostmap declares them as a dict of entries in
settings directly.

```python
# Before: hosts.py (django-hosts)
from django_hosts import host, patterns

host_patterns = patterns(
    "",
    host(r"www", "config.urls_www", name="www"),
    host(r"api", "config.urls_api", name="api"),
)
```

```python
# After: settings.py (django-hostmap)
HOSTMAP = {
    "www": {"subdomain": "www", "urlconf": "config.urls_www"},
    "api": {"subdomain": "api", "urlconf": "config.urls_api"},
}
HOSTMAP_PARENT_DOMAIN = "example.com"  # was ROOT_HOSTCONF / PARENT_HOST
HOSTMAP_DEFAULT = "www"  # was DEFAULT_HOST
```

django-hosts regex patterns that only ever matched a literal label translate
directly to a `subdomain` entry. A pattern using a genuine regex (variable
capture groups, alternation) has no direct hostmap equivalent: hostmap
supports exact hosts and single-level wildcards only (see
[use wildcard subdomains](use-wildcard-subdomains.md)), not arbitrary regex.
If your django-hosts patterns rely on regex capture beyond a single wildcard
label, that is the one part of the migration that needs a design decision
rather than a mechanical translation.

### 2. Swap the middleware

```python
# Before
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "hosts.middleware.HostsRequestMiddleware",
    "django.middleware.common.CommonMiddleware",
    # ...
    "hosts.middleware.HostsResponseMiddleware",  # if used
]

# After
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "hostmap.middleware.HostmapMiddleware",
    "django.middleware.common.CommonMiddleware",
    # ...
]
```

hostmap has no response-side middleware to add; `HostmapMiddleware` does
routing and reversing setup entirely on the request side, before
`get_response()`.

### 3. Update `INSTALLED_APPS`

```python
INSTALLED_APPS = [
    # ...
    # "django_hosts",   # remove
    "hostmap",           # add
]
```

### 4. Leave `{% host_url %}` and `django_hosts.reverse()` in place for now

This is the point of the migration: you do not have to touch every template
or Python call site before the project works. Once `HOSTMAP` and
`HostmapMiddleware` are in place, stock `{% url %}` and `reverse()` are
already host-aware everywhere, including inside third-party apps you never
modified. `{% host_url %}` usages keep working as long as `django_hosts`
itself is still installed and its own resolution still functions
independently; once you are confident hostmap is routing correctly, delete
`{% host_url %}` calls and swap them for `{% url %}` at whatever pace suits
the codebase, since the explicit `host=` argument that django-hosts required
is no longer needed anywhere hostmap's map already covers.

### 5. Remove `django_hosts` once every call site is converted

```bash
pip uninstall django-hosts
```

Then remove it from `INSTALLED_APPS` if it is still listed, and delete
`hosts.py`.

## Verify it worked

```bash
python manage.py check
python manage.py hostmap
```

Confirm the resolved map matches your old `ROOT_HOSTCONF` one-to-one, then
spot-check the URLs that used to go through `{% host_url %}`:

```python
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_migrated_host_resolves_the_same_as_before():
    assert reverse("api:user-detail", args=[7]) == "https://api.example.com/users/7/"
```

## Common pitfalls

- **Trying to keep `ROOT_HOSTCONF`-style regex patterns verbatim.** hostmap
  is deliberately simpler: exact hosts and one-level wildcards, no regex
  capture groups. Most django-hosts patterns are label-literal and translate
  directly; treat any that are not as a design question, not a
  find-and-replace.
- **Deleting `host_url` usages before confirming routing works.** Do the
  middleware and settings swap first, confirm `manage.py hostmap` and a
  handful of real requests behave as expected, then clean up call sites at
  leisure. There is no forcing function to remove them immediately; a shim
  that recreates django-hosts' parallel API was considered and deliberately
  not built, because the migration is already mechanical without one.
- **Forgetting `HOSTMAP_DEFAULT` has no django-hosts equivalent name.** It is
  the same concept as `DEFAULT_HOST`, but it must be set explicitly; there is
  no default default.

## Related

- [Multi-host in ten minutes](../tutorial/multi-host-in-ten-minutes.md): a
  from-scratch walkthrough if you would rather build the map fresh than
  translate an existing one.
- [Settings reference](../reference/settings.md): the full `HOSTMAP_*` table.
