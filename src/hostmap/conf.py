"""Hostmap settings with defaults.

All settings use the ``HOSTMAP_`` prefix. Access via ``hostmap_settings``,
which reads from ``django.conf.settings`` lazily at access time so a test or
consuming project can override a setting after import (04-interfaces.md
section 2). Every setting has a working default per STANDARDS section 4.
"""

from django.conf import settings


def _setting(name, default=None):
    return getattr(settings, name, default)


class _Settings:
    """Lazy settings that read from ``django.conf.settings`` at access time."""

    @property
    def MAP(self):  # noqa: N802
        """The host map dict. Empty map disables all behaviour."""
        return _setting("HOSTMAP", {})

    @property
    def PARENT_DOMAIN(self):  # noqa: N802
        """Domain joined to ``subdomain`` entries."""
        return _setting("HOSTMAP_PARENT_DOMAIN", "")

    @property
    def DEFAULT(self):  # noqa: N802
        """Entry label used for unmatched hosts and out-of-request reversing."""
        return _setting("HOSTMAP_DEFAULT", "")

    @property
    def PATCH_REVERSE(self):  # noqa: N802
        """Make stock ``reverse()`` / ``{% url %}`` host-aware."""
        return _setting("HOSTMAP_PATCH_REVERSE", True)

    @property
    def SCHEME(self):  # noqa: N802
        """Scheme for cross-host absolute URLs."""
        return _setting("HOSTMAP_SCHEME", "https")

    @property
    def PORT(self):  # noqa: N802
        """Port appended to all generated hosts; one port applies uniformly."""
        return _setting("HOSTMAP_PORT", "")

    @property
    def UNMATCHED(self):  # noqa: N802
        """``"default"`` routes unmatched hosts to the default entry; ``"reject"`` returns 404."""
        return _setting("HOSTMAP_UNMATCHED", "default")

    @property
    def REDIRECT_PERMANENT(self):  # noqa: N802
        """``redirect_to`` entries use 301 when true, 302 when false."""
        return _setting("HOSTMAP_REDIRECT_PERMANENT", True)


hostmap_settings = _Settings()
