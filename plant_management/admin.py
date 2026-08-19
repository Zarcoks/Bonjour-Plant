from django.contrib import admin

from .models import AppLog, GrowingPlant, PlantType

admin.site.register(PlantType)
admin.site.register(GrowingPlant)
admin.site.register(AppLog)
