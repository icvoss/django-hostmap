"""The wildcard tenant host's URLconf."""

from django.http import HttpResponse
from django.urls import path


def dashboard(request):
    sub = request.hostmap.subdomain if hasattr(request, "hostmap") else None
    return HttpResponse(f"tenant dashboard: {sub}")


urlpatterns = [
    path("dashboard/", dashboard, name="tenant-dashboard"),
]
