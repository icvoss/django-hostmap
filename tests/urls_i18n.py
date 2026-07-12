"""A per-host URLconf using i18n_patterns (AC-HOSTMAP-007).

Mounted as its own host in the i18n test so routing and reversing through a
locale-prefixed resolver can be exercised without disturbing the main map.
"""

from django.conf.urls.i18n import i18n_patterns
from django.http import HttpResponse
from django.urls import path


def account(request):
    return HttpResponse("account")


urlpatterns = i18n_patterns(
    path("account/", account, name="i18n-account"),
)
