from django.urls import path

from . import views

urlpatterns = [
    path("", views.GrowingPlantList.as_view(), name="growing_plants"),
    path("plants/create/", views.GrowingPlantCreate.as_view(), name="create_growing_plant"),
    path("plants/<int:plant_id>/", views.GrowingPlantDetail.as_view(), name="growing_plant_detail"),
    path("plants/<int:plant_id>/card/", views.GrowingPlantCard.as_view(), name="growing_plant_card"),
    path("plants/<int:plant_id>/delete/", views.GrowingPlantDelete.as_view(), name="delete_growing_plant"),
    path("plants/<int:plant_id>/auto-luminosity/", views.GrowingPlantAutoLuminosity.as_view(),
         name="growing_plant_auto_luminosity"),
]
