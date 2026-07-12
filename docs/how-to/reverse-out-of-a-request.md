# Reverse out of a request

## Goal

Get correct, absolute URLs from Celery tasks, management commands, shells,
email rendering, and webhook payloads, none of which run inside a request
handled by `HostmapMiddleware`.

## Prerequisites

- `HOSTMAP_DEFAULT` set to a valid entry label.
- The code path you are reversing from runs after Django has finished
  starting (so `hostmap`'s `AppConfig.ready()` has installed the seam, if
  `HOSTMAP_PATCH_REVERSE` is on).

## Steps

### 1. Know the default behaviour first

Outside a request, there is no active entry set by `HostmapMiddleware`, so
the active host falls back to `HOSTMAP_DEFAULT`. Reversing behaves exactly as
it would inside a request handled on that host:

```python
# inside a Celery task, a management command, or the shell
from django.urls import reverse

reverse("blog-index")                 # '/blog/' if HOSTMAP_DEFAULT is "www"
reverse("api:user-detail", args=[7])  # absolute, cross-host as usual
```

This is enough for most background code: an email renderer building a link
to the main site needs nothing extra.

### 2. Reach for `use_host()` when the default is not the host you want

`hostmap.urls.use_host()` is a context manager that pins a specific entry (by
label) or a specific concrete host (for wildcard entries) as active for
everything reversed inside it. This is the override for emails, Celery
tasks, API payloads, and webhooks that need a host other than the default.

```python
from hostmap.urls import use_host

with use_host("api"):
    url = reverse("user-detail", args=[7])
# url == "https://api.example.com/users/7/", regardless of HOSTMAP_DEFAULT
```

### 3. Use `build_absolute_uri()` when you want an absolute URL unconditionally

`reverse()` and `{% url %}` only go absolute when the name is cross-host.
When you need an absolute URL even for a same-host name (a password reset
email linking back to the current site, say), use
`hostmap.urls.build_absolute_uri()` instead:

```python
from hostmap.urls import build_absolute_uri

build_absolute_uri("blog-index")
# 'https://www.example.com/blog/', always absolute

build_absolute_uri("api:user-detail", args=[7])
# 'https://api.example.com/users/7/'

build_absolute_uri("/blog/")   # a ready-made path also works
# 'https://www.example.com/blog/'
```

Pin the host explicitly with the `host` parameter, by label or literal host:

```python
build_absolute_uri("user-detail", args=[7], host="api")
build_absolute_uri("dashboard", host="acme.example.com")  # a wildcard host
```

There is deliberately no `absolute=True` parameter on `reverse()` itself;
`build_absolute_uri()` is the one spelling for "I want an absolute URL".

### 4. Use `use_host()` inside a Celery task

```python
# tasks.py
from celery import shared_task

from hostmap.urls import build_absolute_uri, use_host


@shared_task
def send_confirmation_email(order_id, host_label="www"):
    from orders.models import Order

    order = Order.objects.get(id=order_id)
    with use_host(host_label):
        link = build_absolute_uri("orders:detail", args=[order.pk])
    send_mail("Your order", f"View it here: {link}", ...)
```

Pass the host label through as an argument (a plain string, safe to
serialise) rather than trying to propagate hostmap's contextvar into the
worker process; it does not cross process boundaries.

## Verify it worked

```python
from hostmap.urls import build_absolute_uri, reverse, use_host


def test_default_host_is_active_out_of_request(settings):
    assert reverse("blog-index") == "/blog/"


def test_use_host_pins_a_specific_entry():
    with use_host("api"):
        assert reverse("user-detail", args=[7]).startswith("https://api.")


def test_build_absolute_uri_is_always_absolute():
    assert build_absolute_uri("blog-index").startswith("https://")
```

## Common pitfalls

- **Expecting the contextvar to cross into a Celery worker.** It does not;
  `use_host()` is process-local like any other `contextvars.ContextVar`.
  Reconstruct the intended host explicitly inside the task, as shown above.
- **Reaching for `reverse(absolute=True)`.** It does not exist; use
  `build_absolute_uri()` instead. A redundant second spelling for "always
  absolute" was considered and cut.
- **Calling this before Django has finished starting.** Import-time
  `reverse_lazy()` and settings-time reversing (`LOGIN_URL` via
  `resolve_url()`) both work once the app registry is ready, the same as any
  other `reverse()` call; they do not work before that, which is a Django
  constraint, not a hostmap one.

## Related

- [Resolution order](../explanation/resolution-order.md): why the default
  entry is what "out of request" means.
- [API reference](../reference/api.md): full signatures for `reverse`,
  `build_absolute_uri`, and `use_host`.
- [Test host routing](test-host-routing.md): `host_client()` for testing the
  in-request case.
