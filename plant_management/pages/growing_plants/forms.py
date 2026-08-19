from django import forms
from django.utils import timezone

from plant_management.models import GrowingPlant

# What a date input sends back, plus the formats a user could type by hand.
DATE_INPUT_FORMATS = ['%Y-%m-%d', '%Y-%m-%dT%H:%M', '%d/%m/%Y']


def date_field(label):
    """A day, picked in a date input, kept as a timestamp by the model."""
    return forms.DateTimeField(label=label, required=False, input_formats=DATE_INPUT_FORMATS,
                               widget=forms.DateTimeInput(attrs={'type': 'date'}, format='%Y-%m-%d'))


def style_fields(form):
    """Gives every widget of a form its Bootstrap class."""
    for name, field in form.fields.items():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs['class'] = 'form-check-input'
        elif isinstance(field.widget, forms.Select):
            field.widget.attrs['class'] = 'form-select form-select-sm'
        else:
            field.widget.attrs['class'] = 'form-control form-control-sm'


class GrowingPlantForm(forms.ModelForm):
    """Edit form of a growing plant."""
    planted_date = date_field("planté le")
    harvest_day = date_field("récoltée le")

    class Meta:
        model = GrowingPlant
        fields = ['display_name', 'plant_type', 'planted_date', 'harvested', 'harvest_day']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)

    def clean(self):
        cleaned_data = super().clean()
        # The harvest day follows the harvested box: today when the box is ticked
        # without a day, and nothing left behind when the box is unticked.
        if cleaned_data.get('harvested'):
            if not cleaned_data.get('harvest_day'):
                cleaned_data['harvest_day'] = timezone.now()
        else:
            cleaned_data['harvest_day'] = None
        return cleaned_data


class GrowingPlantCreateForm(forms.ModelForm):
    """Creation form: a plant starts its life neither harvested nor measured."""
    planted_date = date_field("planté le")

    class Meta:
        model = GrowingPlant
        fields = ['display_name', 'plant_type', 'planted_date']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
