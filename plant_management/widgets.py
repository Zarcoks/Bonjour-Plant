"""Widgets shared by the forms of the application."""
from django import forms


class PhotoInput(forms.ClearableFileInput):
    """
    The file input of a photo, dressed like the rest of the forms.

    Django's own rendering spells the current file out as a bare link followed
    by a "clear" checkbox, which reads as raw HTML in the middle of a card. This
    one shows the photo itself, and offers to remove it.
    """
    template_name = 'plant_management/widgets/photo_input.html'
