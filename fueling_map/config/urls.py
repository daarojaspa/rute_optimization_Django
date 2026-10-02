"""URL routes."""

from django.urls import URLPattern, URLResolver, include, path

urlpatterns: list[URLPattern | URLResolver] = [path("api/", include("api.urls"))]
