"""Hostmap Django app configuration.

Installs the resolver seam at ``ready()`` and runs a self-test that fails
loudly (``ImproperlyConfigured``) if the seam misbehaves on the running
Django, naming the remediation (03-services.md, seam guards; BR-HOSTMAP-007).
"""

from __future__ import annotations

from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured

# The highest Django feature version this release has been tested against.
# ``hostmap.W004`` warns when the running Django exceeds it (04-interfaces.md).
TESTED_DJANGO_CEILING = (6, 0)


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
        """Reverse a probe through the host-aware resolver to prove the seam works.

        A ``TypeError``/``AttributeError`` here means the ``get_resolver`` /
        ``_reverse_with_prefix`` seam has moved under us; fail startup with the
        remediation rather than let production traffic hit it.
        """
        from django.urls import NoReverseMatch
        from django.urls.resolvers import get_resolver

        try:
            resolver = get_resolver()
            # A probe name that will not resolve: we only assert the seam's
            # method signature holds, not that any URL exists.
            try:
                resolver._reverse_with_prefix("__hostmap_seam_probe__", "/")
            except NoReverseMatch:
                pass
        except (TypeError, AttributeError) as exc:  # pragma: no cover - defensive
            raise ImproperlyConfigured(
                "django-hostmap could not drive Django's URL reverse seam on this "
                f"Django version ({exc}). Set HOSTMAP_PATCH_REVERSE = False to run "
                "routing-only until a compatible django-hostmap release ships."
            ) from exc
