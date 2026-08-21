from django.contrib import admin

from .models import Actionner, AppLog, GrowingPlant, PlantType, Sensor

admin.site.register(PlantType)
admin.site.register(GrowingPlant)
admin.site.register(Sensor)
admin.site.register(Actionner)
admin.site.register(AppLog)
