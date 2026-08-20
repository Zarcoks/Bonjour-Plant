import datetime

from django.db import models
from django.templatetags.static import static
from django.utils import timezone

# The photos shown for a plant type or a sensor that has no picture of its own yet.
DEFAULT_PLANT_TYPE_PHOTO = 'plant-type-default.svg'
DEFAULT_SENSOR_PHOTO = 'sensor-default.svg'

# The keys a measure usually carries in a payload, for a sensor that names them
# the plain way. A sensor naming them otherwise says so on its own fields.
DEFAULT_HUMIDITY_LABEL = 'humidity'
DEFAULT_LUMINOSITY_LABEL = 'luminosity'
DEFAULT_TEMPERATURE_LABEL = 'temperature'

# What a light sensor reports, from the darkest to the brightest, under the names
# the sensors themselves use. The measure is a level, not a duration: how many
# hours of light a species needs a day is the business of its plant type.
LUMINOSITY_LEVELS = ['low-', 'low', 'nor', 'high', 'high+']

# How each level is written in the interface.
LUMINOSITY_LEVEL_NAMES = {
    'low-': "très faible",
    'low': "faible",
    'nor': "normale",
    'high': "forte",
    'high+': "très forte",
}

# From this level up, a plant counts as being in the light rather than in the shade.
WELL_LIT_LEVEL = LUMINOSITY_LEVELS.index('nor')


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
    # The rank of the level in LUMINOSITY_LEVELS, from 0 (low-) to 4 (high+).
    current_luminosity = models.IntegerField("niveau de lumière", null=True, blank=True)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

    def get_photo_url(self):
        """A growing plant is pictured by its type, which falls back to the default illustration."""
        return self.plant_type.get_photo_url()

    def expected_growing_state(self):
        """
        How far along the plant should be, in percent, from what it was planted
        for: the time gone by since it was planted, over the days its species
        takes to be ready.

        The hour counts, so the figure creeps up during the day rather than
        jumping at midnight. Kept between 0 and 100: a plant left in the ground
        past its harvest is ready, not twice ready. None when there is nothing
        to work it out from.
        """
        if self.planted_date is None or not self.plant_type.harvest_days:
            return None
        gone_by = timezone.now() - self.planted_date
        ready_in = datetime.timedelta(days=self.plant_type.harvest_days)
        return max(0, min(100, round(gone_by / ready_in * 100)))

    # The measures below are compared to what the plant type asks for. Each one
    # answers None when the measure is missing: the card then shows no sign at all.
    def get_luminosity_level(self):
        """The level the plant is lit at, None when unknown or off the scale."""
        if self.current_luminosity is None:
            return None
        if not 0 <= self.current_luminosity < len(LUMINOSITY_LEVELS):
            return None
        return LUMINOSITY_LEVELS[self.current_luminosity]

    def get_luminosity_name(self):
        """That level, as the interface writes it."""
        level = self.get_luminosity_level()
        return LUMINOSITY_LEVEL_NAMES[level] if level else None

    def is_well_lit(self):
        """
        Whether the plant sits in the light rather than in the shade.

        Read against a level, not against the hours a day its type asks for:
        the two are different things.
        """
        if self.get_luminosity_level() is None:
            return None
        return self.current_luminosity >= WELL_LIT_LEVEL

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

    # How this sensor names its measures in the payload it publishes.
    humidity_payload_label = models.CharField("humidité (clé du payload)", max_length=120, blank=True,
                                              default=DEFAULT_HUMIDITY_LABEL)
    luminosity_payload_label = models.CharField("luminosité (clé du payload)", max_length=120, blank=True,
                                                default=DEFAULT_LUMINOSITY_LABEL)
    temperature_payload_label = models.CharField("température (clé du payload)", max_length=120, blank=True,
                                                 default=DEFAULT_TEMPERATURE_LABEL)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_photo_url(self):
        if self.photo:
            return self.photo.url
        return static(DEFAULT_SENSOR_PHOTO)

    # A label left empty falls back on the usual name, so that a sensor written
    # outside the interface still reads its payload.
    def get_humidity_label(self):
        return self.humidity_payload_label or DEFAULT_HUMIDITY_LABEL

    def get_luminosity_label(self):
        return self.luminosity_payload_label or DEFAULT_LUMINOSITY_LABEL

    def get_temperature_label(self):
        return self.temperature_payload_label or DEFAULT_TEMPERATURE_LABEL


class SensorData(models.Model):
    """One measure received from a sensor, kept as it came off the broker."""
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='data')
    plant = models.ForeignKey(GrowingPlant, on_delete=models.CASCADE, related_name='sensor_data')
    time = models.DateTimeField(auto_now_add=True)
    payload = models.TextField()

    class Meta:
        ordering = ['-time']

    def __str__(self):
        return "{} : {}".format(self.sensor.name, self.payload)


class AppLog(models.Model):
    """Application-wide activity log."""
    time = models.DateTimeField(auto_now_add=True)
    message = models.CharField(max_length=500)
    type = models.CharField(max_length=60)

    class Meta:
        ordering = ['-time']

    def __str__(self):
        return "[{}] {}".format(self.type, self.message)
