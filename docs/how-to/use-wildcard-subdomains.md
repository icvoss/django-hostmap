# Use wildcard subdomains

## Goal

Route an unbounded set of subdomains (one per customer, one per workspace)
to a single URLconf, and understand the one place wildcard entries behave
differently from ordinary entries: reversing into a specific subdomain.

## Prerequisites

- `HOSTMAP_PARENT_DOMAIN` set (wildcard entries are always `subdomain`
  entries, never `host` entries).

## Steps

### 1. Add a `subdomain: "*"` entry

```python
# settings.py
HOSTMAP = {
    "www": {"subdomain": "www", "urlconf": "config.urls.www"},
    "tenant": {"subdomain": "*", "urlconf": "config.urls.tenant"},
}
HOSTMAP_PARENT_DOMAIN = "example.com"
HOSTMAP_DEFAULT = "www"
```

`tenant` now matches exactly one subdomain level under
`example.com`: `acme.example.com`, `globex.example.com`, and so on.
`acme.staging.example.com` does **not** match; wildcards capture exactly one
label, never a nested path.

Exact entries always beat wildcards during matching, so a literal entry for
one specific subdomain (say, a reserved `status.example.com`) takes
precedence over the wildcard even if both are declared.

### 2. Read the captured subdomain from `request.hostmap`

Inside a request routed by the wildcard entry, `request.hostmap.subdomain`
carries the captured label; `request.hostmap.label` is still just `"tenant"`
(the entry's own label, not the customer's).

```python
# config/urls_tenant.py views
def dashboard(request):
    customer = request.hostmap.subdomain  # e.g. "acme"
    ...
```

For non-wildcard entries, `request.hostmap.subdomain` is always `None`.
There is no bare `request.subdomain`; the namespaced object avoids the
collision other packages historically caused by claiming that name directly.

### 3. Know that wildcards never participate in cross-host reversing automatically

A name that only exists on the wildcard URLconf will not be found by the
default cross-host fallback search, because there is no single concrete host
to fall back to; the fallback order only considers the active host, the
default entry, and other named entries in declaration order (see
[resolution order](../explanation/resolution-order.md)).

To reverse into a specific tenant's subdomain, pin the concrete host
explicitly with `use_host(host=...)`:

```python
from hostmap.urls import use_host

with use_host(host="acme.example.com"):
    url = reverse("dashboard")
# url == "https://acme.example.com/dashboard/"
```

`use_host` recognises `acme.example.com` as a concrete instance of the
`tenant` wildcard entry and reverses against its URLconf. This is the one
place a wildcard host needs to be named explicitly; there is no way to
reverse "into the wildcard" without saying which subdomain you mean, because
the wildcard itself is not a single host.

## Verify it worked

```python
import pytest


@pytest.mark.django_db
def test_wildcard_subdomain_routes(client):
    response = client.get("/dashboard/", HTTP_HOST="acme.example.com")
    assert response.status_code == 200


def test_request_hostmap_captures_the_subdomain(client):
    response = client.get("/dashboard/", HTTP_HOST="acme.example.com")
    assert response.wsgi_request.hostmap.subdomain == "acme"
    assert response.wsgi_request.hostmap.label == "tenant"


def test_use_host_reverses_into_a_wildcard_host():
    from hostmap.urls import reverse, use_host

    with use_host(host="acme.example.com"):
        assert reverse("dashboard") == "https://acme.example.com/dashboard/"
```

## Common pitfalls

- **Expecting a multi-level subdomain to match.** `subdomain: "*"` captures
  exactly one label; `a.b.example.com` does not match a wildcard entry for
  `example.com`.
- **Expecting `reverse("dashboard")` to pick a tenant automatically.**
  Wildcard entries are not a single host, so there is no default to fall
  back to; you must supply `use_host(host=...)`.
- **Confusing wildcard routing with multi-tenancy.** hostmap only routes the
  request and exposes the captured subdomain; it does none of the tenant
  resolution, row scoping, or database routing that a package like
  django-boundary provides. Combine the two by configuration (a wildcard
  entry here, a subdomain-based tenant resolver there), never by import.

## Related

- [Route a subdomain to its own URLconf](route-a-subdomain-to-its-own-urlconf.md):
  ordinary, non-wildcard entries.
- [Resolution order](../explanation/resolution-order.md): why wildcards are
  excluded from the cross-host fallback order.
- [API reference](../reference/api.md): `use_host()` signature, including the
  `host=` parameter.
