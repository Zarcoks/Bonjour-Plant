from django import forms

from Logging import LEVELS


class LogFilterForm(forms.Form):
    """The filters of the log page. Every field is optional: no field means no filter."""
    search = forms.CharField(label="recherche", required=False,
                             widget=forms.TextInput(attrs={'placeholder': "un mot du message…"}))
    type = forms.ChoiceField(label="niveau", required=False,
                             choices=[('', "tous les niveaux")] + [(level, level) for level in LEVELS])
    date = forms.DateField(label="date", required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css_class = 'form-select form-select-sm' if name == 'type' else 'form-control form-control-sm'
            field.widget.attrs['class'] = css_class

    def filter(self, logs):
        """Narrows a log queryset down to what the filled filters ask for."""
        if not self.is_valid():
            return logs
        if self.cleaned_data.get('search'):
            logs = logs.filter(message__icontains=self.cleaned_data['search'])
        if self.cleaned_data.get('type'):
            logs = logs.filter(type=self.cleaned_data['type'])
        if self.cleaned_data.get('date'):
            logs = logs.filter(time__date=self.cleaned_data['date'])
        return logs
