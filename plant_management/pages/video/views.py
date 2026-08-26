from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views import View

from core.app import app
from plant_management.models import Camera

from . import photo

logger = app.module_logger("video")

# Where the templates of this page live.
TEMPLATES = 'plant_management/video/'


def cameras():
    """Every camera to pick from, the ones out of reach included but greyed out."""
    return Camera.objects.filter(is_deleted=False)


def picked(request):
    """The camera the page is asked for, or None when none is."""
    asked = request.GET.get('camera')
    if not asked:
        return None
    return Camera.objects.filter(pk=asked, is_deleted=False).first()


class VideoPage(View):
    """
    The video page: a camera to pick at the top, its last photograph underneath.

    Answers the picture alone to an HTMX request, which is how picking another
    camera, and how the refresh button, work without reloading the page.
    """

    def get(self, request):
        camera = picked(request)
        context = {
            'cameras': cameras(),
            'camera': camera,
            # What makes the address of the photograph change from one refresh
            # to the next, so that the browser goes and asks for it again.
            'taken_at': timezone.now().timestamp(),
        }
        if request.headers.get('HX-Request'):
            return render(request, TEMPLATES + 'partials/photo.html', context)
        return render(request, TEMPLATES + 'video.html', context)


class CameraPhoto(View):
    """
    One photograph of one camera, taken when it is asked for.

    Nothing is kept: the picture is taken, handed over, and forgotten. A camera
    that could not be photographed answers 502 — the page shows the broken
    picture and its own words beside it.
    """

    def get(self, request, camera_id):
        camera = get_object_or_404(Camera, pk=camera_id, is_deleted=False)
        if not camera.is_supported():
            raise Http404("Ce modèle de caméra n'est pas pris en charge")
        taken = photo.take(camera)
        if taken is None:
            return HttpResponse("La photo n'a pas pu être prise", status=502)
        answer = HttpResponse(taken, content_type='image/jpeg')
        # Every refresh is a new photograph: none of them is worth keeping.
        answer['Cache-Control'] = 'no-store'
        return answer
