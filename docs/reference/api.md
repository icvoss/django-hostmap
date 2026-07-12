# API reference

The explicit API (`hostmap.urls`) for code that needs host-aware reversing
outside a request, or an absolute URL unconditionally, plus the testing
helpers in `hostmap.testing`.

---

## `hostmap.urls`

### `reverse(name, args=None, kwargs=None) -> str`

Host-aware reverse with the same semantics as the patched stock `reverse()`:
resolves against the active host first, and returns a path if the name
resolves there, or an absolute URL if resolution falls through to another
entry. This is the same resolution logic the resolver seam uses; calling
this function directly is equivalent to calling `django.urls.reverse()` when
`HOSTMAP_PATCH_REVERSE` is `True`, and is the only host-aware option when it
is `False`.

```python
from hostmap.urls import reverse

reverse("blog-index")                 # '/blog/'
reverse("api:user-detail", args=[7])  # 'https://api.example.com/users/7/'
reverse("api:user-detail", kwargs={"pk": 7})
```

Raises `django.urls.NoReverseMatch`, naming every host searched, if the name
resolves on no configured entry.

---

### `build_absolute_uri(name_or_path, args=None, kwargs=None, host=None) -> str`

The single explicit entry point for an absolute URL regardless of the active
host. Accepts either a URL name (reversed with `args` / `kwargs`) or a
ready-made path starting with `/`.

```python
from hostmap.urls import build_absolute_uri

build_absolute_uri("blog-index")
# 'https://www.example.com/blog/'   — absolute even though this name
#                                       resolves on the active host

build_absolute_uri("api:user-detail", args=[7])
# 'https://api.example.com/users/7/'

build_absolute_uri("/blog/")
# 'https://www.example.com/blog/'   — a ready-made path also works

build_absolute_uri("user-detail", args=[7], host="api")
# pins the "api" entry explicitly by label

build_absolute_uri("dashboard", host="acme.example.com")
# pins a concrete host under a wildcard entry
```

`host` accepts either a map label or a literal host string; a literal host
is matched against exact entries first, then against wildcard entries (in
which case the concrete host borrows the wildcard's URLconf). Raises
`NoReverseMatch` if `host` matches no entry and no wildcard.

There is deliberately no `absolute=True` parameter on `reverse()`; a
redundant second spelling for "always absolute" was considered and cut in
favour of this one function.

---

### `use_host(label=None, host=None)`

Context manager. Everything reversed inside treats the given entry (by
`label`) or literal host (by `host`, for a concrete instance of a wildcard
entry) as active. This is the override for emails, Celery tasks, API
payloads, and webhooks that need a specific host regardless of
`HOSTMAP_DEFAULT` or whatever request context (if any) is running.

```python
from hostmap.urls import use_host
from django.urls import reverse

with use_host("api"):
    reverse("user-detail", args=[7])
    # 'https://api.example.com/users/7/', "api" active regardless of default

with use_host(host="acme.example.com"):
    reverse("dashboard")
    # reverses against the wildcard entry matching this concrete host
```

Pass exactly one of `label` or `host`. Yields the resolved entry. Restores
the previous active entry (and Django's `urlconf`) on exit, including on
exception, via the same contextvar token mechanism Python's `contextvars`
module provides.

---

## `hostmap.testing`

### `host_client(label, **kwargs) -> django.test.Client`

Returns a Django test `Client` with `SERVER_NAME` set to the given entry's
effective host, so every request the client makes routes through
`HostmapMiddleware` to that host's URLconf. Extra keyword arguments pass
through to `Client` unchanged.

```python
from hostmap.testing import host_client

client = host_client("api")
response = client.get("/users/7/")
```

Raises `KeyError` if `label` is not a known `HOSTMAP` label. Raises
`ValueError` if `label` is a wildcard entry: a wildcard has no single
concrete host, so use a plain `Client(SERVER_NAME=...)` with an explicit
concrete host instead (see
[test host routing](../how-to/test-host-routing.md)).

---

### pytest fixtures

Import into your project's `conftest.py`:

```python
# conftest.py
from hostmap.testing.fixtures import *  # noqa: F401,F403
```

This exposes:

| Fixture | Type | Behaviour |
|---------|------|-----------|
| `host_client` | factory fixture | Call as `host_client("api")` inside a test; returns the same object `hostmap.testing.host_client()` would |

```python
def test_api_host_serves_user_detail(db, host_client):
    client = host_client("api")
    response = client.get("/users/7/")
    assert response.status_code == 200
```

---

### `use_host` (re-export)

`hostmap.testing` re-exports `use_host` from `hostmap.urls` so tests can pin
the active host for a `reverse()` assertion without needing a full request:

```python
from hostmap.testing import use_host
from django.urls import reverse


def test_reverse_into_api_host():
    with use_host("api"):
        assert reverse("user-detail", args=[7]) == "https://api.example.com/users/7/"
```

Scope of `hostmap.testing` is fixed deliberately at `host_client`, the
fixture, and this re-export: no `RequestFactory` wrapper, no bundled
assertion helpers.

---

## Related

- [Reverse out of a request](../how-to/reverse-out-of-a-request.md): using
  this API from Celery tasks, management commands, and email rendering.
- [Test host routing](../how-to/test-host-routing.md): using `host_client()`
  and the pytest fixture in practice.
- [Settings reference](settings.md): every `HOSTMAP_*` setting this API
  reads.
