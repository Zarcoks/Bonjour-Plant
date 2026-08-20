from django.urls import path

from . import views

urlpatterns = [
    path("", views.Metrics.as_view(), name="metrics"),
]
