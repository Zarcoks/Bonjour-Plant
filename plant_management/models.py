from django.db import models
from django.templatetags.static import static

# The photos shown for a plant type or a sensor that has no picture of its own yet.
DEFAULT_PLANT_TYPE_PHOTO = 'plant-type-default.svg'
DEFAULT_SENSOR_PHOTO = 'sensor-default.svg'


class PlantType(models.Model):
    """A plant species known by the application, with its ideal growing conditions."""
    plant_name = models.CharField("nom", max_length=120)
    humidity_min = models.IntegerField("humidité min. (%)")
    humidity_max = models.IntegerField("humidité max. (%)")
    temperature_min = models.FloatField("temp. min. (°C)")
    temperature_max = models.FloatField("temp. max. (°C)")
    luminosity_per_day = models.IntegerField("luminosité / jour (h)")
    harvest_days = models.IntegerField("jours avant récolte")
    photo = models.ImageField("photo", upload_to='plant_types/', blank=True)

    class Meta:
        ordering = ['plant_name']

    def __str__(self):
        return self.plant_name

    def get_photo_url(self):
        if self.photo:
            return self.photo.url
        return static(DEFAULT_PLANT_TYPE_PHOTO)

    def get_humidity_range(self):
        return "{} – {} %".format(self.humidity_min, self.humidity_max)

    def get_temperature_range(self):
        return "{} – {} °C".format(self.temperature_min, self.temperature_max)


class GrowingPlant(models.Model):
    """An actual plant being grown by the user, of a given plant type."""
    display_name = models.CharField("nom", max_length=120)
    plant_type = models.ForeignKey(PlantType, verbose_name="type de plante", on_delete=models.CASCADE,
                                   related_name='growing_plants')
    planted_date = models.DateTimeField("planté le", null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    harvested = models.BooleanField("récoltée", default=False)
    harvest_day = models.DateTimeField("récoltée le", null=True, blank=True)
    last_watering = models.DateTimeField("dernier arrosage", null=True, blank=True)
    auto_luminosity = models.BooleanField("lumière automatique", default=False)

    growing_state = models.IntegerField("avancement (%)", default=0)
    current_temperature = models.FloatField("température actuelle", null=True, blank=True)
    current_humidity = models.IntegerField("humidité actuelle", null=True, blank=True)
    current_luminosity = models.IntegerField("luminosité actuelle", null=True, blank=True)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

    def get_photo_url(self):
        """A growing plant is pictured by its type, which falls back to the default illustration."""
        return self.plant_type.get_photo_url()

    # The measures below are compared to what the plant type asks for. Each one
    # answers None when the measure is missing: the card then shows no sign at all.
    def has_enough_light(self):
        if self.current_luminosity is None:
            return None
        return self.current_luminosity >= self.plant_type.luminosity_per_day

    def is_too_hot(self):
        if self.current_temperature is None:
            return None
        return self.current_temperature > self.plant_type.temperature_max

    def is_too_cold(self):
        if self.current_temperature is None:
            return None
        return self.current_temperature < self.plant_type.temperature_min

    def needs_water(self):
        if self.current_humidity is None:
            return None
        return self.current_humidity < self.plant_type.humidity_min


class Sensor(models.Model):
    """A sensor of the installation, assigned to a growing plant or to none."""
    name = models.CharField("nom", max_length=120)
    model = models.CharField("modèle", max_length=120)
    is_deleted = models.BooleanField(default=False)
    plant = models.ForeignKey(GrowingPlant, verbose_name="assigné à", on_delete=models.SET_NULL,
                              null=True, blank=True, related_name='sensors')
    mqtt_topic = models.CharField("topic MQTT", max_length=200)
    photo = models.ImageField("photo", upload_to='sensors/', blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_photo_url(self):
        if self.photo:
            return self.photo.url
        return static(DEFAULT_SENSOR_PHOTO)


class AppLog(models.Model):
    """Application-wide activity log."""
    time = models.DateTimeField(auto_now_add=True)
    message = models.CharField(max_length=500)
    type = models.CharField(max_length=60)

    class Meta:
        ordering = ['-time']

    def __str__(self):
        return "[{}] {}".format(self.type, self.message)
