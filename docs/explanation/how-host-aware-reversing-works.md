# How host-aware reversing works

This document explains why hostmap can make stock `reverse()`, `reverse_lazy()`
and `{% url %}` host-aware everywhere, including inside third-party apps you
never touch, without changing a single call site. Read it to understand the
resolver-acquisition seam, why same-host reversing costs nothing, the
runtime guards that protect you across Django upgrades, and the one contract
change `reverse()` now carries.

For exhaustive option tables, see the [settings reference](../reference/settings.md).
For task-focused guides, see the [how-to directory](../how-to/).

## The problem: patching `reverse` itself does not work

The obvious approach, rebind `django.urls.reverse` to a host-aware wrapper at
startup, fails for a structural reason. Third-party apps bind
`from django.urls import reverse` at their own module import time, which
happens during Django's app registry population, before any
`AppConfig.ready()` runs. Once that binding exists, it is a direct reference
to the original function object. Rebinding `django.urls.reverse` afterwards
changes nothing for code already holding that reference; the app already has
its own name pointing at the old function.

This is exactly the problem django-hosts has always had. Its answer was an
explicit parallel API: its own `reverse()`, a `{% host_url %}` template tag,
and a `host=` argument at call sites that need cross-host links. That works,
but it means every call site, including ones inside third-party apps you do
not control, has to be found and rewritten. django-admin's own reversing,
for instance, cannot be fixed this way at all.

## The seam: resolver acquisition, not `reverse` itself

hostmap looks one layer deeper. Django's `reverse()` does not do resolution
itself; it delegates to a `URLResolver` object, acquired fresh on every call
via `get_resolver(urlconf)`. That acquisition call is not early-bound the way
`reverse` is: it happens inside `reverse()`'s body, every time, using
whatever `get_resolver` currently is at call time. hostmap replaces
`get_resolver`, in both `django.urls.resolvers` (where it is defined) and
`django.urls.base` (which early-binds its own reference to it, so both need
patching), with a wrapper.

For the active host's URLconf, the wrapper returns a `HostAwareResolver`, a
`URLResolver` subclass whose `_reverse_with_prefix` retries the other hosts'
resolvers on `NoReverseMatch` and returns an absolute URL for a cross-host
match. Every other URLconf, importantly including the fallback targets
themselves, gets the ordinary stock resolver back untouched. This
asymmetry matters: if the fallback resolvers were also wrapped, a miss on
one host would recurse into checking every other host's `HostAwareResolver`,
which would in turn check every other host again. Keeping the fallback
resolvers plain means the search is a single flat pass, never a recursive
one.

Because the seam sits below `reverse`, not at it, every caller reaches it:
your own views, third-party apps, and `django.contrib.admin`, all calling
plain `django.urls.reverse()`, all resolve through the same `get_resolver`
your project's settings configured.

## Why same-host reversing is free

The resolver seam only matters when a name does not resolve on the active
host. For same-host reversing, there is nothing to patch at all: hostmap's
middleware sets `request.urlconf` to the matched entry's URLconf, and Django's
own request handling calls `set_urlconf()` with that value. Stock
`reverse()` resolves `urlconf=None` via `get_urlconf()`, which now returns
the active host's URLconf natively. `HostAwareResolver._reverse_with_prefix`
tries the ordinary Django resolution first and only falls into cross-host
fallback on `NoReverseMatch`; a same-host success never touches the fallback
path at all.

This is what makes the compatibility guarantee (BR-HOSTMAP-003 in the
package's specification) hold: a name that resolves on the active host
returns a path byte-identical to what stock, unpatched Django would return,
because the code path that produces it *is* stock Django, all the way down.
Single-host projects, and same-host links inside multi-host projects, see no
behaviour change whatsoever.

The active host itself lives in a `contextvars.ContextVar`, not a thread
local, mirroring how Django's own `urlconf` propagates under ASGI. Setting
the active entry also calls `set_urlconf()` directly, so this holds even
outside a request, for example inside `use_host()`.

## Runtime guards: protecting you across Django upgrades

Hooking `get_resolver` is a private-API dependency: nothing guarantees
Django's internals stay stable across versions. hostmap treats this
honestly rather than pretending it away, with two layers of defence:

**At development time**, the package's own CI matrix runs the comparison
suite against every supported Django version, with a dedicated test that
pins the seam's observed behaviour, so a maintainer sees an internals move
as a loud test failure, never a silent regression.

**At your runtime**, CI protects the maintainer, not a user whose Django
upgrade lands in production before a compatible django-hostmap release
exists. Two guards close that gap:

1. At `AppConfig.ready()`, immediately after installing the patch, a
   self-test reverses a probe URL pattern through the host-aware resolver.
   If the seam's expected method signature does not hold (a `TypeError` or
   `AttributeError`), startup fails immediately with
   `ImproperlyConfigured`, naming the remediation directly in the error
   message: set `HOSTMAP_PATCH_REVERSE = False` until a compatible release
   ships. A loud failure at deploy time beats a subtle one in production
   traffic.
2. System check `hostmap.W004` warns when the running Django version is
   newer than the package's declared tested ceiling, even if the self-test
   still passes. This is advance notice: a version bump that happens to
   still work today is not guaranteed to keep working, and the warning
   tells you to test the upgrade in a branch rather than assume.

See [turn off reversing](../how-to/turn-off-reversing.md) for what actually
happens when you flip that setting.

## The one contract change: `reverse()` may return an absolute URL

Once the patch is installed, `reverse()` can return an absolute URL
(`https://api.example.com/users/7/`) where stock Django always returns a
path (`/users/7/`). This is a real, deliberate contract change, not an
accident, and it is worth being honest about rather than glossing over.

It is safe in practice because every code path Django itself uses to consume
`reverse()` output already tolerates an absolute URL:
`HttpResponseRedirect` and the `redirect()` shortcut both accept one,
`resolve_url()` passes an absolute URL through unchanged, and
`request.build_absolute_uri()` and `iri_to_uri()` do too. The package's
comparison suite asserts this directly against each of those consumers
rather than merely assuming it holds across Django versions.

Where it can bite is code outside Django's own machinery that assumed
`reverse()` always returns a path, for example naive string concatenation
like `"/static-prefix" + reverse(...)`. That assumption was always slightly
fragile (Django's own `SCRIPT_NAME` handling could already produce surprises
under `FORCE_SCRIPT_NAME`); hostmap makes it visible rather than causing it.

## Verify your understanding

- A single-host project with `HOSTMAP` unset (or empty) behaves exactly like
  a project with no hostmap installed at all: an empty map disables
  `HostmapMiddleware`'s routing entirely, and `HOSTMAP_PATCH_REVERSE` never
  installs the seam without at least one entry, so `reverse()` is
  byte-identical to stock Django.
- A third-party app's own `reverse()` call, imported at its module's own
  top level before hostmap's `ready()` ever runs, still resolves correctly
  cross-host, because the seam lives beneath `reverse`, not inside the name
  the app imported.
- Turning off `HOSTMAP_PATCH_REVERSE` never breaks routing; only reversing
  reverts to stock behaviour, and the explicit API keeps working because it
  calls the same resolution logic the patch would have used, not a second
  implementation.

These are exactly the properties the package's comparison suite and
third-party-app simulation test exist to pin down.

## Related

- [Resolution order](resolution-order.md): the precise order cross-host
  fallback searches in, and what happens on no match.
- [Turn off reversing](../how-to/turn-off-reversing.md): the escape hatch and
  what it changes and does not change.
- [Reverse out of a request](../how-to/reverse-out-of-a-request.md): the
  explicit API that shares this same resolution logic.
- [Settings reference](../reference/settings.md#hostmap_patch_reverse):
  `HOSTMAP_PATCH_REVERSE` and the `hostmap.W004` check.
