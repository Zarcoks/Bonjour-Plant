from django.urls import path

from . import views

urlpatterns = [
    path("", views.PlantTypeList.as_view(), name="plant_types"),
    path("create/", views.PlantTypeCreate.as_view(), name="create_plant_type"),
    path("<int:plant_type_id>/", views.PlantTypeDetail.as_view(), name="plant_type_detail"),
    path("<int:plant_type_id>/card/", views.PlantTypeCard.as_view(), name="plant_type_card"),
]
