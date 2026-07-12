"""The www host's URLconf (also ROOT_URLCONF / default entry)."""

from django.http import HttpResponse
from django.urls import path


def home(request):
    return HttpResponse("www home")


def blog_index(request):
    return HttpResponse("blog")


urlpatterns = [
    path("", home, name="home"),
    path("blog/", blog_index, name="blog-index"),
]
