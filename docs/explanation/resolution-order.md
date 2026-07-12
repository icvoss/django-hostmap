# Resolution order

This document explains the exact order hostmap searches hosts in when
reversing a URL name, why that order is fixed rather than configurable per
call, and what happens when a name resolves on no host at all. Read it
alongside [how host-aware reversing works](how-host-aware-reversing-works.md)
for the mechanism this order runs inside.

## The order, precisely

Cross-host resolution tries hosts in this fixed sequence:

1. **The active host.** Inside a request, this is the entry
   `HostmapMiddleware` matched for the current request. Outside a request,
   it is the `HOSTMAP_DEFAULT` entry. Inside `use_host()`, it is whatever
   that context manager pinned.
2. **The default entry** (`HOSTMAP_DEFAULT`), if it was not already the
   active host.
3. **Every remaining entry, in `HOSTMAP` declaration order.**

The first entry whose URLconf resolves the name wins. This is why `HOSTMAP`
declaration order is meaningful: if a URL name happens to exist on two
non-default, non-active hosts, the one declared first in the dict wins the
tie.

Redirect entries (`redirect_to`) and wildcard entries (`subdomain: "*"`)
never participate in this search. A redirect entry has no URLconf of its own
to try. A wildcard entry has no single concrete host to be absolute
*against*, so it is skipped; reversing into a specific subdomain under a
wildcard requires the explicit `use_host(host=...)` form (see
[use wildcard subdomains](../how-to/use-wildcard-subdomains.md)).

Duplicate entries are removed from the search while preserving first sight,
so the active host (if it also happens to be the default) is only tried
once.

## Why the order is fixed, not a per-call argument

An earlier design considered letting call sites influence resolution order,
or accept a `host=` argument the way django-hosts does. Both were rejected.
A fixed order means every `reverse()` call in the codebase, including ones
inside third-party apps, gets the same, predictable behaviour with zero
configuration at the call site. If you need a specific host regardless of
this order, that is exactly what `use_host()` and `build_absolute_uri(host=...)`
are for: an explicit override, used deliberately, rather than an implicit
parameter threaded through every call.

## Same-host wins over "also exists elsewhere"

Because the active host is always tried first, a URL name that happens to be
declared on more than one host's URLconf (two apps both defining a view
called `"home"`, say) resolves to the *active* host's version whenever you
are reversing from a request on that host. Only when the active host's
URLconf does not have the name at all does the search fall through to the
default, then to the rest of the map.

This means the same `reverse("home")` call can validly return different
results depending on which host is active when it runs, which is
precisely the point: hostmap makes reversing host-aware, not host-blind.

## `NoReverseMatch` and the searched-hosts message

If no entry in the search order resolves the name, hostmap raises
`django.urls.NoReverseMatch`, the same exception type stock Django already
raises and that third-party code already catches. The message names every
host that was searched, so a failure is diagnosable without reaching for
`manage.py hostmap`:

```
NoReverseMatch: Reverse for 'nonexistent-view' not found on any hostmap
host. Searched: www.example.com, api.example.com.
```

Template `{% url ... as var %}` keeps Django's usual silent-failure
contract through this: on no match, the template variable is simply left
unassigned, exactly as stock Django behaves for a name that does not
resolve at all. See
[link across hosts in templates and Python](../how-to/link-across-hosts-in-templates-and-python.md).

## Cached, not recomputed per call

Per-entry resolvers are built once and cached, so the fallback search is a
single pass over already-resolved, already-cached resolver objects, not a
rebuild on every `reverse()` call. Both resolution paths in the package,
the explicit API (`hostmap.urls.reverse` / `build_absolute_uri`) and the
resolver seam (`HostAwareResolver._cross_host_reverse`), consume the same
`entry_order()` function, so there is exactly one implementation of this
ordering to reason about, never two that could drift out of sync.

## Worked example

Given:

```python
HOSTMAP = {
    "www": {"subdomain": "www", "urlconf": "config.urls_www"},
    "api": {"subdomain": "api", "urlconf": "config.urls_api"},
    "apex": {"host": "example.com", "redirect_to": "www"},
}
HOSTMAP_DEFAULT = "www"
```

With `www` active:

| Call | Result | Why |
|------|--------|-----|
| `reverse("blog-index")` | `/blog/` | Resolves on the active host (`www`); byte-identical to stock Django |
| `reverse("user-detail", args=[7])` | `https://api.example.com/users/7/` | Not on `www`; falls through to `api`, the next entry in declaration order |
| `reverse("nowhere")` | raises `NoReverseMatch` | Not found on `www` or `api`; `apex` is a redirect entry and is never searched |
| Same calls from a Celery task | identical results | `www` (the default) is active outside a request |

## Related

- [How host-aware reversing works](how-host-aware-reversing-works.md): the
  mechanism this order runs inside, and why same-host reversing is free.
- [Use wildcard subdomains](../how-to/use-wildcard-subdomains.md): why
  wildcard entries are excluded from this search.
- [Reverse out of a request](../how-to/reverse-out-of-a-request.md):
  `use_host()` as the explicit override to this order.
