from django.urls import path

from . import views

urlpatterns = [
    path("", views.VideoPage.as_view(), name="video"),
    path("create/", views.CameraCreate.as_view(), name="create_camera"),
    path("<int:camera_id>/edit/", views.CameraUpdate.as_view(), name="edit_camera"),
    path("<int:camera_id>/delete/", views.CameraDelete.as_view(), name="delete_camera"),
]
