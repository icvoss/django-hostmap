"""The api host's URLconf."""

from django.http import HttpResponse
from django.urls import path


def user_detail(request, pk):
    return HttpResponse(f"user {pk}")


urlpatterns = [
    path("users/<int:pk>/", user_detail, name="user-detail"),
]
