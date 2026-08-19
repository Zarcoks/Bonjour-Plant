from django.urls import path

from . import views

urlpatterns = [
    path("", views.LogList.as_view(), name="logs"),
]
