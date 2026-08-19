from django.urls import path

from . import views

urlpatterns = [
    path("", views.SensorList.as_view(), name="sensors"),
    path("create/", views.SensorCreate.as_view(), name="create_sensor"),
    path("<int:sensor_id>/", views.SensorDetail.as_view(), name="sensor_detail"),
    path("<int:sensor_id>/card/", views.SensorCard.as_view(), name="sensor_card"),
    path("<int:sensor_id>/delete/", views.SensorDelete.as_view(), name="delete_sensor"),
]
