# Add a redirect host

## Goal

Redirect one host to another, preserving the full path and query string:
the classic case is redirecting the bare apex domain (`example.com`) to
`www.example.com`.

## Prerequisites

- `HOSTMAP` configured with at least one non-redirect entry to redirect to.

## Steps

### 1. Add a `redirect_to` entry

A redirect entry sets `redirect_to` instead of `urlconf`. It names the label
of a non-redirect entry (`hostmap.E003` fails startup if an entry has both or
neither of `urlconf` / `redirect_to`).

```python
# settings.py
HOSTMAP = {
    "www": {"subdomain": "www", "urlconf": "config.urls.www"},
    "apex": {"host": "example.com", "redirect_to": "www"},
}
HOSTMAP_PARENT_DOMAIN = "example.com"
HOSTMAP_DEFAULT = "www"
```

`apex` here is a `host` entry (the bare parent domain), not a `subdomain`
entry, since it has no subdomain label of its own.

### 2. Choose permanent or temporary redirects

`HOSTMAP_REDIRECT_PERMANENT` (default `True`) controls the status code for
every redirect entry:

```python
HOSTMAP_REDIRECT_PERMANENT = True   # 301, the default: browsers and
                                     # search engines cache this
HOSTMAP_REDIRECT_PERMANENT = False  # 302, useful while you are still
                                     # deciding the final host
```

This is a single project-wide setting, not per-entry: every redirect entry
in the map uses the same status code.

### 3. Confirm redirect targets cannot chain

`redirect_to` must name a non-redirect entry. Redirecting one redirect entry
to another fails startup as `hostmap.E004`, because chained redirects are
never useful and hostmap refuses to let them accumulate silently.

```python
# This fails hostmap.E004: "apex2" points at "apex", which is itself a
# redirect entry.
HOSTMAP = {
    "www": {"subdomain": "www", "urlconf": "config.urls.www"},
    "apex": {"host": "example.com", "redirect_to": "www"},
    "apex2": {"host": "old.example.com", "redirect_to": "apex"},  # E004
}
```

Point `apex2` at `www` directly instead.

## Verify it worked

```bash
curl -i http://example.com/blog/?ref=newsletter
```

You should see:

```
HTTP/1.1 301 Moved Permanently
Location: https://www.example.com/blog/?ref=newsletter
```

Both the path (`/blog/`) and the query string (`?ref=newsletter`) are
preserved; only the host changes.

```python
import pytest


@pytest.mark.django_db
def test_apex_redirects_to_www(client):
    response = client.get("/blog/?ref=newsletter", HTTP_HOST="example.com")
    assert response.status_code == 301
    assert response["Location"] == "https://www.example.com/blog/?ref=newsletter"
```

## Common pitfalls

- **Chaining redirects.** `hostmap.E004` catches this at startup; point
  every redirect entry directly at its final, non-redirect target.
- **Expecting a per-entry status code.** `HOSTMAP_REDIRECT_PERMANENT` is
  global. If you need a mix of 301 and 302 across different hosts, that is
  out of scope; handle it with a view on the redirecting host's own URLconf
  instead of a `redirect_to` entry.
- **Forgetting the redirect target itself needs `ALLOWED_HOSTS` coverage
  too.** Both the redirecting host and the target host must be in
  `ALLOWED_HOSTS`.

## Related

- [Route a subdomain to its own URLconf](route-a-subdomain-to-its-own-urlconf.md):
  for entries that route rather than redirect.
- [Settings reference](../reference/settings.md): `HOSTMAP_REDIRECT_PERMANENT`
  and the `hostmap.E004` check.
