from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from core.app import app
from plant_management.models import Camera

from .forms import CameraForm

logger = app.module_logger("video")

# Where the templates of this page live.
TEMPLATES = 'plant_management/video/'

# The event asking the page to load its cameras again.
REFRESH_EVENT = 'refresh-cameras'


def cameras():
    """The cameras the page shows: never the deleted ones."""
    return Camera.objects.filter(is_deleted=False)


def watched(request):
    """
    The camera the page plays: the one asked for, else the first declared.

    Landing on the page shows a picture rather than an invitation to pick one;
    an address naming a camera that is gone falls back the same way.
    """
    asked = request.GET.get('camera')
    if asked:
        return cameras().filter(pk=asked).first() or cameras().first()
    return cameras().first()


def stage(camera):
    """Everything the page shows: the cameras to pick from, and the one playing."""
    return {'cameras': cameras(), 'camera': camera}


class VideoPage(View):
    """
    The video page: the cameras of the installation on the left, one playing.

    Answers the stage alone to an HTMX request, which is how picking another
    camera, and how a creation or a deletion, are taken into account without
    reloading the page.
    """

    def get(self, request):
        context = stage(watched(request))
        if request.headers.get('HX-Request'):
            return render(request, TEMPLATES + 'partials/stage.html', context)
        return render(request, TEMPLATES + 'video.html', context)


# Where the form is written, whether it creates a camera or changes one.
FORM_CONTAINER = '#camera-form'


def form_page(request, form, camera=None):
    """The form alone, as it is first opened and as it comes back refused."""
    return render(request, TEMPLATES + 'partials/camera_form.html',
                  {'form': form, 'camera': camera})


def refused(request, form, camera=None):
    """
    The form again, in its own container rather than in the stage.

    Both the creation and the edition are posted from above the stage but
    answered into it: what comes back wrong has to be sent home by hand.
    """
    response = form_page(request, form, camera)
    response['HX-Retarget'] = FORM_CONTAINER
    response['HX-Reswap'] = 'innerHTML'
    return response


class CameraCreate(View):
    """The creation form, and the creation itself."""

    def get(self, request):
        return form_page(request, CameraForm())

    def post(self, request):
        form = CameraForm(request.POST)
        # Invalid input: the form goes back to its own container instead of the stage.
        if not form.is_valid():
            logger.warning("La création d'une caméra a été refusée")
            return refused(request, form)
        camera = form.save()
        logger.info("La caméra " + camera.name + " a été ajoutée sur " + camera.stream_url)
        # A camera is added to be watched: the page plays it straight away.
        return render(request, TEMPLATES + 'partials/camera_saved.html', stage(camera))


class CameraUpdate(View):
    """
    The same form, filled with a camera, and the change itself.

    Changing the address of a camera is changing what is played: the answer
    comes back on that camera, so that the new address is watched at once
    rather than at the next click on it.
    """

    def get(self, request, camera_id):
        camera = get_object_or_404(Camera, pk=camera_id, is_deleted=False)
        return form_page(request, CameraForm(instance=camera), camera)

    def post(self, request, camera_id):
        camera = get_object_or_404(Camera, pk=camera_id, is_deleted=False)
        form = CameraForm(request.POST, instance=camera)
        if not form.is_valid():
            logger.warning("La modification de la caméra " + camera.name + " a été refusée")
            return refused(request, form, camera)
        camera = form.save()
        logger.info("La caméra " + camera.name + " a été modifiée")
        return render(request, TEMPLATES + 'partials/camera_saved.html', stage(camera))


class CameraDelete(View):
    """
    Removes a camera from the application. The row is kept, flagged as deleted.

    Nothing is swapped in place: the answer asks the page to load its cameras
    again, which also settles what is playing when the one deleted was it.
    """

    def post(self, request, camera_id):
        camera = get_object_or_404(Camera, pk=camera_id, is_deleted=False)
        camera.is_deleted = True
        camera.save()
        logger.info("La caméra " + camera.name + " a été supprimée")
        response = HttpResponse(status=204)
        response['HX-Trigger'] = REFRESH_EVENT
        return response
