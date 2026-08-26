from django.urls import path

from . import views

urlpatterns = [
    path("", views.VideoPage.as_view(), name="video"),
    path("photo/<int:camera_id>/", views.CameraPhoto.as_view(), name="camera_photo"),
]
