"""Hostmap Django app configuration.

Installs the resolver seam at ``ready()`` and runs a self-test that fails
loudly (``ImproperlyConfigured``) if the seam misbehaves on the running
Django, naming the remediation (03-services.md, seam guards; BR-HOSTMAP-007).
"""

from __future__ import annotations

from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured

# The highest Django feature version this release has been tested against.
# ``hostmap.E009`` (patch active) or ``hostmap.W004`` (patch off) fires when
# the running Django exceeds it (04-interfaces.md, icvoss/django-hostmap#4).
#
# Raised to (6, 1) after verifying the seam directly (icvoss/django-hostmap#9):
# ``django/urls/resolvers.py`` and the rest of the ``django/urls`` package are
# byte-identical between Django 6.0.8 and 6.1, and the 6.1 release notes make
# no mention of ``django.urls``, resolvers, or reversing. ``_reverse_with_prefix``
# keeps its signature and behaviour, so the patch needed no adaptation.
TESTED_DJANGO_CEILING = (6, 1)


class HostmapConfig(AppConfig):
    name = "hostmap"
    label = "hostmap"
    verbose_name = "Hostmap"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from hostmap import checks  # noqa: F401  registers system checks
        from hostmap.conf import hostmap_settings

        if not hostmap_settings.PATCH_REVERSE:
            return
        if not hostmap_settings.MAP:
            return

        from hostmap import resolvers

        resolvers.install()
        self._seam_self_test()

    def _seam_self_test(self):
        """Prove the resolver seam's BEHAVIOUR, not just its call signature.

        Builds two throwaway, in-memory URLconfs (never touching the
        consumer's own URLs) and drives ``HostAwareResolver._reverse_with_prefix``
        directly against them: a same-host reverse must stay a bare path
        (unaffected by the override), and a cross-host reverse (a name that
        only exists on the second, "fallback" URLconf) must return the exact
        expected ``scheme://host/path`` absolute URL. A signature-only probe
        (calling the method and catching ``NoReverseMatch``) proves the
        method still accepts its arguments; it does not prove the override
        still composes the right result. This proves the composition too:
        a seam that silently returns a wrong host, a mangled path, or a
        same-host hit it should not have touched fails an equality
        assertion here, not just an exception check.

        What this CANNOT prove: that ``get_resolver()`` is wired to return a
        ``HostAwareResolver`` for the consumer's *real* active URLconf (that
        wiring is ``resolvers.install()``'s job); that the consumer's own
        URL names resolve correctly end-to-end through a real request; or
        anything about ``get_resolver``'s caching/threading behaviour beyond
        what a direct call exercises. Those are covered by the test suite
        (``tests/test_seam_pin.py``, ``tests/test_comparison.py``,
        ``tests/test_routing.py``), not by a ready()-time check that must
        stay fast and self-contained.

        A ``TypeError``/``AttributeError`` means the ``_reverse_with_prefix``
        seam has moved under us; any other mismatch (wrong URL, unexpected
        exception) means it still runs but no longer behaves as expected.
        Either way, fail startup with the remediation rather than let
        production traffic hit it.
        """
        from django.http import HttpResponse
        from django.urls import NoReverseMatch, path
        from django.urls.resolvers import RegexPattern

        from hostmap import urls as hostmap_urls
        from hostmap.conf import hostmap_settings
        from hostmap.map import ResolvedEntry
        from hostmap.resolvers import HostAwareResolver

        def _seam_probe_view(request):  # pragma: no cover - never actually called
            return HttpResponse()

        active_name = "__hostmap_seam_active_probe__"
        cross_host_name = "__hostmap_seam_cross_host_probe__"
        cross_host_path = "/__hostmap_seam_cross_host_probe__/"

        # Two throwaway, in-memory URLconfs (tuples, never a module on disk):
        # the active one carries a name the fallback one does not, so a
        # reverse for that name is guaranteed to miss on the active resolver
        # and fall through to cross-host resolution. A tuple, not a list,
        # because the fallback resolver is acquired through Django's own
        # cached get_resolver(), which requires a hashable urlconf key.
        active_urlconf = (path("active-probe/", _seam_probe_view, name=active_name),)
        fallback_urlconf = (path(cross_host_path.strip("/") + "/", _seam_probe_view, name=cross_host_name),)

        fallback_host = "hostmap-seam-self-test-fallback.invalid"
        active_entry = ResolvedEntry(
            label="__hostmap_seam_active_entry__",
            host="hostmap-seam-self-test-active.invalid",
            urlconf=active_urlconf,
            redirect_to=None,
            wildcard=False,
        )
        fallback_entry = ResolvedEntry(
            label="__hostmap_seam_fallback_entry__",
            host=fallback_host,
            urlconf=fallback_urlconf,
            redirect_to=None,
            wildcard=False,
        )
        # Composed independently of hostmap.urls._absolute_url (the function
        # the real cross-host path itself calls) rather than by calling it:
        # if that helper were the one that broke, comparing its own output
        # against itself would pass vacuously. This mirrors the consumer's
        # HOSTMAP_SCHEME / HOSTMAP_PORT settings (the only two inputs
        # _absolute_url composes with) without importing its logic.
        expected_host = f"{fallback_host}:{hostmap_settings.PORT}" if hostmap_settings.PORT else fallback_host
        expected_cross_host_url = f"{hostmap_settings.SCHEME}://{expected_host}{cross_host_path}"

        original_entry_order = hostmap_urls.entry_order
        try:
            hostmap_urls.entry_order = lambda: [active_entry, fallback_entry]
            resolver = HostAwareResolver(RegexPattern(r"^/"), active_urlconf)

            same_host_result = resolver._reverse_with_prefix(active_name, "/")
            if same_host_result != "/active-probe/":
                raise ImproperlyConfigured(
                    "django-hostmap's seam self-test found the resolver seam mangling a "
                    f"same-host reverse (got {same_host_result!r}, expected '/active-probe/') "
                    "on this Django version. Set HOSTMAP_PATCH_REVERSE = False to run "
                    "routing-only until a compatible django-hostmap release ships."
                )

            cross_host_result = resolver._reverse_with_prefix(cross_host_name, "/")
            if cross_host_result != expected_cross_host_url:
                raise ImproperlyConfigured(
                    "django-hostmap's seam self-test found the resolver seam's cross-host "
                    f"reverse returning an unexpected result (got {cross_host_result!r}, "
                    f"expected {expected_cross_host_url!r}) on this Django version. The "
                    "private URLResolver._reverse_with_prefix seam this package hooks may "
                    "have changed behaviour. Set HOSTMAP_PATCH_REVERSE = False to run "
                    "routing-only until a compatible django-hostmap release ships."
                )
        except NoReverseMatch as exc:
            raise ImproperlyConfigured(
                "django-hostmap's seam self-test could not reverse its own throwaway probe "
                f"patterns on this Django version ({exc}). The resolver seam this package "
                "hooks may have changed behaviour. Set HOSTMAP_PATCH_REVERSE = False to run "
                "routing-only until a compatible django-hostmap release ships."
            ) from exc
        except (TypeError, AttributeError) as exc:
            raise ImproperlyConfigured(
                "django-hostmap could not drive Django's URL reverse seam on this "
                f"Django version ({exc}). Set HOSTMAP_PATCH_REVERSE = False to run "
                "routing-only until a compatible django-hostmap release ships."
            ) from exc
        finally:
            hostmap_urls.entry_order = original_entry_order
