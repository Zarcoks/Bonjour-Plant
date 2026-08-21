from django import forms

from plant_management.models import PlantType
from plant_management.widgets import PhotoInput


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
            'light_starts_at',
            'light_ends_at',
            'photo',
        ]
        widgets = {'photo': PhotoInput}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control form-control-sm'
            # An hour of the day is picked in a time input.
            if name in ('light_starts_at', 'light_ends_at'):
                field.widget.input_type = 'time'

    def clean(self):
        cleaned_data = super().clean()
        humidity_min, humidity_max = cleaned_data.get('humidity_min'), cleaned_data.get('humidity_max')
        if humidity_min is not None and humidity_max is not None and humidity_min > humidity_max:
            self.add_error('humidity_max', "L'humidité maximale doit être supérieure à l'humidité minimale.")
        temperature_min, temperature_max = cleaned_data.get('temperature_min'), cleaned_data.get('temperature_max')
        if temperature_min is not None and temperature_max is not None and temperature_min > temperature_max:
            self.add_error('temperature_max', "La température maximale doit être supérieure à la température minimale.")
        starts_at, ends_at = cleaned_data.get('light_starts_at'), cleaned_data.get('light_ends_at')
        if starts_at is not None and ends_at is not None and starts_at >= ends_at:
            self.add_error('light_ends_at', "La fin de la lumière doit être après son début.")
        return cleaned_data
