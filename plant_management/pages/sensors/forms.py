from django import forms

from plant_management.models import GrowingPlant, Sensor


class SensorForm(forms.ModelForm):
    """Create / edit form of a sensor, including the plant it is assigned to."""

    class Meta:
        model = Sensor
        fields = ['name', 'model', 'mqtt_topic', 'plant', 'photo']

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
