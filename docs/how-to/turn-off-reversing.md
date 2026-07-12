# Turn off reversing

## Goal

Disable the resolver-acquisition patch and fall back to routing-only, either
as a temporary escape hatch (a Django upgrade lands before a compatible
django-hostmap release) or as a deliberate, permanent choice for a project
that only wants host-based routing.

## Prerequisites

- None; this is a single setting.

## Steps

### 1. Set `HOSTMAP_PATCH_REVERSE = False`

```python
# settings.py
HOSTMAP_PATCH_REVERSE = False
```

With the patch off:

- **Routing keeps working exactly as before.** `HostmapMiddleware` still
  matches the host, sets `request.urlconf`, populates `request.hostmap`, and
  handles `redirect_to` entries. None of that depends on the reverse patch.
- **Stock `reverse()` and `{% url %}` revert to ordinary Django behaviour.**
  Cross-host names that used to come back as absolute URLs now raise
  `NoReverseMatch` if they do not resolve on the active host's URLconf, the
  same as they would with no hostmap installed at all.
- **The explicit API keeps working.** `hostmap.urls.reverse()`,
  `build_absolute_uri()`, and `use_host()` call the same resolution logic the
  patch would have used; there are never two implementations to keep in
  lockstep, so turning off the patch does not touch this code path at all.

### 2. Know when this happens automatically, versus when you choose it

This is the documented remediation for two situations:

1. **A Django upgrade breaks the seam.** At `AppConfig.ready()`, hostmap runs
   a self-test that reverses a probe pattern through the resolver seam. If
   Django's internals have moved in a way the seam cannot handle, startup
   fails with `ImproperlyConfigured` naming this setting as the fix. This is
   a deliberate hard failure: better a loud startup error than a subtly
   broken production deploy.
2. **A newer, not-yet-broken Django version.** `hostmap.W004` warns at
   startup when the running Django is newer than the package's tested
   ceiling, even if the seam self-test still passes. This is advance notice,
   not an error; you can keep running with the patch on, but if reversing
   starts misbehaving you already know the likely cause and the fix.

### 3. Migrate existing cross-host links if you turn this off permanently

If you are choosing routing-only deliberately (not as a temporary
workaround), audit any template or Python code relying on the old cross-host
absolute URLs and switch those specific call sites to the explicit API:

```python
from hostmap.urls import build_absolute_uri

build_absolute_uri("api:user-detail", args=[7])
```

This still gives you an absolute, cross-host URL where you need one; only
the automatic behaviour of stock `reverse()` is gone.

## Verify it worked

```python
import pytest
from django.urls import NoReverseMatch, reverse


@pytest.mark.django_db
def test_stock_reverse_no_longer_crosses_hosts(settings):
    settings.HOSTMAP_PATCH_REVERSE = False
    with pytest.raises(NoReverseMatch):
        reverse("api:user-detail", args=[7])  # assuming this only exists on "api"


@pytest.mark.django_db
def test_routing_still_works(client, settings):
    settings.HOSTMAP_PATCH_REVERSE = False
    response = client.get("/users/7/", SERVER_NAME="api.example.com")
    assert response.status_code == 200


def test_explicit_api_still_works(settings):
    settings.HOSTMAP_PATCH_REVERSE = False
    from hostmap.urls import build_absolute_uri

    assert build_absolute_uri("api:user-detail", args=[7]).startswith("https://api.")
```

Note that `HOSTMAP_PATCH_REVERSE` is read once at `AppConfig.ready()` to
decide whether to install the seam; flipping it via `settings` in a live test
process does not retroactively install or remove the patch. Override it in
your settings module before the app starts (or accept that a test flipping
it mid-process is exercising the explicit API's independence from the patch,
not a live toggle of the patch itself).

## Common pitfalls

- **Expecting flipping the setting at runtime to install or remove the
  patch.** The patch is installed once, at `AppConfig.ready()`. Change this
  setting in your settings module before the process starts, not by mutating
  `settings` mid-run and expecting the seam to appear or disappear.
- **Assuming routing also breaks.** It does not; only reversing is affected.
  This is the whole point of the escape hatch: a broken seam should degrade
  to "cross-host links are relative-only", never to "the site is down".
- **Ignoring `hostmap.W004`.** It is advance warning, not an error. Treat it
  as a prompt to test the upgrade in a branch before it reaches production,
  per [the operational notes in the verification spec](../troubleshooting.md).

## Related

- [How host-aware reversing works](../explanation/how-host-aware-reversing-works.md):
  why the seam exists and what the self-test protects against.
- [Reverse out of a request](reverse-out-of-a-request.md): the explicit API
  that keeps working regardless of this setting.
- [Settings reference](../reference/settings.md): `HOSTMAP_PATCH_REVERSE` and
  the `hostmap.W004` check.
