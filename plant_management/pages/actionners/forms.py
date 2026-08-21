from django import forms
from django.utils import timezone

from plant_management.models import Actionner, GrowingPlant
from plant_management.widgets import PhotoInput


class ActionnerForm(forms.ModelForm):
    """Create / edit form of an actionner, including what it acts on."""

    class Meta:
        model = Actionner
        fields = ['name', 'act_on', 'mqtt_topic_out', 'mqtt_topic_in', 'state_payload_label',
                  'plant', 'is_on', 'photo']
        widgets = {'photo': PhotoInput}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # An actionner is assigned to a plant, or to none at all.
        self.fields['plant'].label = "assigner à"
        self.fields['plant'].required = False
        self.fields['plant'].empty_label = "aucune plante"
        self.fields['plant'].queryset = GrowingPlant.objects.filter(is_deleted=False)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select form-select-sm'
            else:
                field.widget.attrs['class'] = 'form-control form-control-sm'

    def save(self, commit=True):
        actionner = super().save(commit=False)
        # Switching it on or off is what the date of the last switch is about.
        if actionner.is_on != self.initial.get('is_on', False):
            actionner.last_switch = timezone.now()
        if commit:
            actionner.save()
        return actionner
