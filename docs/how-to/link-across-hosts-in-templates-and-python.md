# Link across hosts in templates and Python

## Goal

Understand what `{% url %}` and `reverse()` return once hostmap is
installed, so you can rely on them the same way you always have, in
templates and in Python, without an explicit host at any call site.

## Prerequisites

- `HOSTMAP` configured with at least two entries.
- `HOSTMAP_PATCH_REVERSE` at its default (`True`). If it is `False`, see
  [turn off reversing](turn-off-reversing.md) instead: stock `reverse()` is
  unpatched and only the [explicit API](reverse-out-of-a-request.md) is
  host-aware.

## Steps

### 1. Use `{% url %}` exactly as you always have

No template changes, no new tag, no `host=` argument:

```django
{# templates/nav.html #}
<a href="{% url 'blog-index' %}">Blog</a>
<a href="{% url 'api:user-detail' request.user.pk %}">My API profile</a>
```

If `blog-index` resolves on the active host, you get a relative path
(`/blog/`), byte-identical to what stock Django would render. If
`api:user-detail` only resolves on the `api` host, you get an absolute URL
(`https://api.example.com/users/7/`). The template author does not need to
know, or care, which case applies.

### 2. Use `reverse()` exactly as you always have in Python

```python
from django.urls import reverse

reverse("blog-index")               # '/blog/'
reverse("api:user-detail", args=[7])  # 'https://api.example.com/users/7/'
```

This is stock `django.urls.reverse`, not a hostmap wrapper. It works
identically inside your own views and inside third-party apps you have not
touched, because hostmap hooks resolver acquisition rather than rebinding
`reverse` itself. See
[how host-aware reversing works](../explanation/how-host-aware-reversing-works.md)
for the mechanism.

### 3. Know the silent-failure contract still holds

`{% url ... as var %}` keeps Django's usual silent-failure behaviour through
the cross-host fallback: if the name resolves on no host at all, the
template assigns nothing to `var` rather than raising.

```django
{% url 'maybe-missing' as maybe_link %}
{% if maybe_link %}<a href="{{ maybe_link }}">Link</a>{% endif %}
```

Without `as`, a name that resolves on no configured host raises
`NoReverseMatch`, naming every host that was searched, exactly like stock
Django names the URLconf it searched.

### 4. Know when a result is absolute versus relative

Anything downstream that already tolerates an absolute URL from `reverse()`
continues to work unmodified: `HttpResponseRedirect`, the `redirect()`
shortcut, `resolve_url()`, and `request.build_absolute_uri()` all accept
absolute input. If you have code that assumes `reverse()` always returns a
path (for example, string concatenation like `"/prefix" + reverse(...)`),
that assumption was already fragile; hostmap surfaces it rather than causing
it.

## Verify it worked

```python
import pytest
from django.urls import reverse

from hostmap import context


@pytest.mark.django_db
def test_same_host_reverse_is_relative(settings):
    assert reverse("blog-index") == "/blog/"


@pytest.mark.django_db
def test_cross_host_reverse_is_absolute(settings):
    url = reverse("api:user-detail", args=[7])
    assert url.startswith("https://api.")
```

Use [`host_client()`](test-host-routing.md) to exercise this through a real
request against a specific host.

## Common pitfalls

- **Assuming `reverse()` always returns a path.** It may return an absolute
  URL once a cross-host name is reversed. Code that concatenates onto
  `reverse()` output should be audited once, the same way you would audit any
  library upgrade that changes a return type.
- **Expecting `{% url %}` to raise inside `as`.** It never does; that is
  stock Django template behaviour, unchanged.
- **Forgetting the active host is what "same-host" means.** "Same-host" is
  relative to whichever entry is active for the current reverse call, not
  necessarily the entry the template happens to render under. Out of a
  request, the active host is the default entry; see
  [resolution order](../explanation/resolution-order.md).

## Related

- [How host-aware reversing works](../explanation/how-host-aware-reversing-works.md):
  the resolver-acquisition seam and why third-party apps need no changes.
- [Resolution order](../explanation/resolution-order.md): the exact order
  cross-host fallback searches in.
- [Reverse out of a request](reverse-out-of-a-request.md): pinning the
  active host explicitly with `use_host()`.
