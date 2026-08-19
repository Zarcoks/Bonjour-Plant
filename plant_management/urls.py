"""Routes every page of the application, one included URLconf per page."""
from django.urls import include, path

urlpatterns = [
    path("", include("plant_management.pages.home.urls")),
    path("plant-types/", include("plant_management.pages.plant_types.urls")),
    path("logs/", include("plant_management.pages.logs.urls")),
]
