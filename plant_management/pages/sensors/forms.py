from django import forms

from plant_management.models import GrowingPlant, Sensor

# The keys the sensor reads its measures under, in the order the form shows them.
PAYLOAD_LABEL_FIELDS = [
    'humidity_payload_label',
    'luminosity_payload_label',
    'temperature_payload_label',
]


class SensorForm(forms.ModelForm):
    """Create / edit form of a sensor, including the plant it is assigned to."""

    class Meta:
        model = Sensor
        fields = ['name', 'model', 'mqtt_topic', 'plant'] + PAYLOAD_LABEL_FIELDS + ['photo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A sensor is assigned to a plant, or to none at all.
        self.fields['plant'].label = "assigner à"
        self.fields['plant'].required = False
        self.fields['plant'].empty_label = "aucune plante"
        self.fields['plant'].queryset = GrowingPlant.objects.filter(is_deleted=False)
        for name, field in self.fields.items():
            css_class = 'form-select form-select-sm' if name == 'plant' else 'form-control form-control-sm'
            field.widget.attrs['class'] = css_class

    def clean(self):
        cleaned_data = super().clean()
        # A label left empty goes back to the usual name of the measure.
        for name in PAYLOAD_LABEL_FIELDS:
            if not cleaned_data.get(name):
                cleaned_data[name] = Sensor._meta.get_field(name).default
        return cleaned_data
