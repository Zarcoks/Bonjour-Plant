from django import forms

from plant_management.models import GrowingPlant


class PlantChoiceField(forms.ModelChoiceField):
    """Names a harvested plant as such, so the choice is not misleading."""

    def label_from_instance(self, plant):
        return plant.display_name + (" (récoltée)" if plant.harvested else "")


class PlantPickerForm(forms.Form):
    """Which plant the page shows. Harvested plants are offered too."""
    plant = PlantChoiceField(label="plante", required=False, empty_label=None,
                             queryset=GrowingPlant.objects.filter(is_deleted=False),
                             widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))

    def chosen(self):
        """The plant asked for, the first one otherwise, None when there is none."""
        if self.is_valid() and self.cleaned_data.get('plant'):
            return self.cleaned_data['plant']
        return self.fields['plant'].queryset.first()
