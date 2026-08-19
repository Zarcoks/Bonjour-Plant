from django import forms

from plant_management.models import PlantType


class PlantTypeForm(forms.ModelForm):
    """Create / edit form for a plant type, styled with the Bootstrap form classes."""

    class Meta:
        model = PlantType
        fields = [
            'plant_name',
            'harvest_days',
            'humidity_min',
            'humidity_max',
            'temperature_min',
            'temperature_max',
            'luminosity_per_day',
            'photo',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control form-control-sm'

    def clean(self):
        cleaned_data = super().clean()
        humidity_min, humidity_max = cleaned_data.get('humidity_min'), cleaned_data.get('humidity_max')
        if humidity_min is not None and humidity_max is not None and humidity_min > humidity_max:
            self.add_error('humidity_max', "L'humidité maximale doit être supérieure à l'humidité minimale.")
        temperature_min, temperature_max = cleaned_data.get('temperature_min'), cleaned_data.get('temperature_max')
        if temperature_min is not None and temperature_max is not None and temperature_min > temperature_max:
            self.add_error('temperature_max', "La température maximale doit être supérieure à la température minimale.")
        return cleaned_data
