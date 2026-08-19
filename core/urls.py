"""
URL configuration for the Bonjour Plant project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("plant_management.urls")),
]

# In development, Django serves the user uploads itself.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
