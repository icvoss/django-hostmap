# Test host routing

## Goal

Write tests that exercise a specific host in your `HOSTMAP`, using
`hostmap.testing.host_client()` and the bundled pytest fixture.

## Prerequisites

- pytest and pytest-django, if you are using the fixture form.
- `HOSTMAP` configured with the entries you want to test.

## Steps

### 1. Use `host_client()` directly

`hostmap.testing.host_client(label)` returns an ordinary Django test
`Client` with `SERVER_NAME` already set to that entry's effective host, so
every request it makes routes through `HostmapMiddleware` to the right
URLconf.

```python
from hostmap.testing import host_client


def test_api_host_serves_user_detail(db):
    client = host_client("api")
    response = client.get("/users/7/")
    assert response.status_code == 200
```

Extra keyword arguments pass straight through to `Client`:

```python
client = host_client("api", enforce_csrf_checks=True)
```

An unknown label raises `KeyError` naming the labels that do exist; a
wildcard label raises `ValueError`, since a wildcard entry has no single
concrete host (see step 3).

### 2. Use the pytest fixture instead of importing directly

Add the fixtures to your `conftest.py`:

```python
# conftest.py
from hostmap.testing.fixtures import *  # noqa: F401,F403
```

Then `host_client` is available as a factory fixture in any test:

```python
def test_www_host_serves_home(db, host_client):
    client = host_client("www")
    response = client.get("/")
    assert response.status_code == 200


def test_api_host_serves_user_detail(db, host_client):
    client = host_client("api")
    response = client.get("/users/7/")
    assert response.status_code == 200
```

### 3. Testing a wildcard entry needs a concrete host, not a label

`host_client()` requires a single concrete host to set `SERVER_NAME` to;
a wildcard entry (`subdomain: "*"`) has no single host, so
`host_client("tenant")` raises `ValueError`. Use a plain `Client` with an
explicit `SERVER_NAME` for the concrete subdomain you want to test instead:

```python
from django.test import Client


def test_wildcard_tenant_routes(db):
    client = Client(SERVER_NAME="acme.example.com")
    response = client.get("/dashboard/")
    assert response.status_code == 200
```

### 4. Test reversing with `use_host`

`hostmap.testing` re-exports `use_host` so tests can pin the active host for
a `reverse()` assertion without going through a request at all:

```python
from hostmap.testing import use_host
from django.urls import reverse


def test_reverse_into_api_host():
    with use_host("api"):
        assert reverse("user-detail", args=[7]) == "https://api.example.com/users/7/"
```

## Verify it worked

Run the tests above; `host_client()` and the fixture form should behave
identically, since the fixture is a thin wrapper over the same function.

## Common pitfalls

- **Using a plain `RequestFactory` and expecting hostmap routing.**
  `RequestFactory` never runs through middleware. Use `host_client()` (which
  wraps a real `Client`, so `HostmapMiddleware` runs) when you need routing
  behaviour; use `RequestFactory` only when you are testing a view function
  in isolation and setting `request.urlconf` / `request.hostmap` yourself.
- **Calling `host_client()` with a wildcard label.** It raises `ValueError`
  by design; pass a concrete `SERVER_NAME` to a plain `Client` instead.
- **Forgetting `db` (or `django_db`) on tests that hit a view touching the
  database.** This is ordinary pytest-django behaviour, not specific to
  hostmap, but easy to forget when the failure looks host-related.

## Related

- [API reference](../reference/api.md): `host_client()` and fixture
  signatures.
- [Use wildcard subdomains](use-wildcard-subdomains.md): why wildcard entries
  need a concrete host at test time.
