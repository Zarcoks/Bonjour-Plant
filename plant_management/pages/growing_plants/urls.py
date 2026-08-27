from django.urls import path

from . import views

urlpatterns = [
    path("", views.GrowingPlantList.as_view(), name="growing_plants"),
    path("warnings/", views.Warnings.as_view(), name="warnings"),
    path("warnings/<str:subject>/<int:device_id>/<str:kind>/dismiss/", views.DismissWarning.as_view(),
         name="dismiss_warning"),
    path("plants/create/", views.GrowingPlantCreate.as_view(), name="create_growing_plant"),
    path("plants/<int:plant_id>/", views.GrowingPlantDetail.as_view(), name="growing_plant_detail"),
    path("plants/<int:plant_id>/card/", views.GrowingPlantCard.as_view(), name="growing_plant_card"),
    path("plants/<int:plant_id>/delete/", views.GrowingPlantDelete.as_view(), name="delete_growing_plant"),
    path("plants/<int:plant_id>/auto-luminosity/", views.GrowingPlantAutoLuminosity.as_view(),
         name="growing_plant_auto_luminosity"),
    path("plants/<int:plant_id>/auto-watering/", views.GrowingPlantAutoWatering.as_view(),
         name="growing_plant_auto_watering"),
]
