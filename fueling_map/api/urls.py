from django.urls import path

from api.views import route_view

urlpatterns = [path("route/", route_view)]
