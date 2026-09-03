from urllib.parse import urlsplit

from django import forms

from plant_management.models import Camera, GrowingPlant

# The schemes a browser can be sent to. A camera is declared under the address
# its stream is served on, which is an HTTP one: RTSP is what MediaMTX reads on
# the local network, never what a page plays.
BROWSER_SCHEMES = ('http', 'https')


class CameraForm(forms.ModelForm):
    """
    Create form of a camera: a name, and the address its stream is served on.

    The address is the one of the Raspberry Pi, not of the camera: the page
    plays what MediaMTX republishes.
    """

    class Meta:
        model = Camera
        fields = ['name', 'stream_url', 'plant']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['stream_url'].help_text = "Par exemple http://192.168.1.42:8888/jardin/index.m3u8"
        # A camera watches a plant, or nothing in particular.
        self.fields['plant'].label = "assigner à"
        self.fields['plant'].required = False
        self.fields['plant'].empty_label = "aucune plante"
        self.fields['plant'].queryset = GrowingPlant.objects.filter(is_deleted=False)
        for name, field in self.fields.items():
            css_class = 'form-select form-select-sm' if name == 'plant' else 'form-control form-control-sm'
            field.widget.attrs['class'] = css_class

    def clean_stream_url(self):
        """
        The address, checked for the two things a browser cannot do without.

        A scheme it can follow, and a machine to follow it to. What comes after
        is taken as it is written: the address is the one the user watches the
        stream on, and they are the one who knows what it looks like.
        """
        address = self.cleaned_data['stream_url'].strip()
        parts = urlsplit(address)
        if parts.scheme not in BROWSER_SCHEMES or not parts.hostname:
            raise forms.ValidationError("L'adresse doit commencer par http:// ou https:// et porter une machine.")
        return address
