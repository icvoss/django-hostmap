"""``manage.py hostmap``: print the resolved map (04-interfaces.md section 4)."""

from django.core.management.base import BaseCommand

from hostmap.conf import hostmap_settings
from hostmap.map import resolved_entries


class Command(BaseCommand):
    help = "Print the resolved hostmap: each entry's effective host, URLconf, and redirect target."

    def handle(self, *args, **options):
        entries = resolved_entries()
        if not entries:
            self.stdout.write("HOSTMAP is empty; hostmap is disabled.")
            return

        default = hostmap_settings.DEFAULT
        self.stdout.write(f"Parent domain: {hostmap_settings.PARENT_DOMAIN or '(none)'}")
        self.stdout.write(f"Default entry: {default or '(unset)'}")
        self.stdout.write(f"Scheme: {hostmap_settings.SCHEME}   Port: {hostmap_settings.PORT or '(none)'}")
        self.stdout.write("")

        for label, entry in entries.items():
            marker = " *default*" if label == default else ""
            self.stdout.write(f"{label}{marker}")
            self.stdout.write(f"    host:     {entry.host}{'  (wildcard)' if entry.wildcard else ''}")
            if entry.is_redirect:
                self.stdout.write(f"    redirect: -> {entry.redirect_to}")
            else:
                self.stdout.write(f"    urlconf:  {entry.urlconf}")
