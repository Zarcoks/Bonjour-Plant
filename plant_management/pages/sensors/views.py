from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from core.app import app
from mqtt_worker import feedback
from plant_management.models import Sensor

from .forms import SensorForm

logger = app.module_logger("sensors")

# Where the templates of this page live.
TEMPLATES = 'plant_management/sensors/'

# The event asking the page to load its grid again.
REFRESH_EVENT = 'refresh-sensors'


def sensors():
    """The sensors the page shows: never the deleted ones."""
    return Sensor.objects.filter(is_deleted=False).select_related('plant')


class SensorList(View):
    """
    Full page: every sensor of the installation, as a grid of cards.

    Answers the grid alone to an HTMX request, which is how the page loads its
    sensors again after a deletion.
    """

    def get(self, request):
        context = {'sensors': sensors()}
        if request.headers.get('HX-Request'):
            return render(request, TEMPLATES + 'partials/sensors_grid.html', context)
        return render(request, TEMPLATES + 'sensors.html', context)


class SensorCard(View):
    """The collapsed card of a sensor (also used to cancel an edition)."""

    def get(self, request, sensor_id):
        sensor = get_object_or_404(Sensor, pk=sensor_id, is_deleted=False)
        return render(request, TEMPLATES + 'partials/sensor_card.html', {'sensor': sensor})


class SensorDetail(View):
    """The expanded card: every field of the sensor, editable in place."""

    def get(self, request, sensor_id):
        sensor = get_object_or_404(Sensor, pk=sensor_id, is_deleted=False)
        return render(request, TEMPLATES + 'partials/sensor_detail.html',
                      {'sensor': sensor, 'form': SensorForm(instance=sensor)})

    def post(self, request, sensor_id):
        sensor = get_object_or_404(Sensor, pk=sensor_id, is_deleted=False)
        form = SensorForm(request.POST, request.FILES, instance=sensor)
        # Invalid input: send the edition form back, so the user keeps their changes.
        if not form.is_valid():
            logger.warning("La modification du capteur " + sensor.name + " a été refusée")
            return render(request, TEMPLATES + 'partials/sensor_detail.html',
                          {'sensor': sensor, 'form': form})
        sensor = form.save()
        logger.info("Le capteur " + sensor.name + " a été modifié, assigné à "
                    + (sensor.plant.display_name if sensor.plant else "aucune plante"))
        return render(request, TEMPLATES + 'partials/sensor_card.html', {'sensor': sensor})


class SensorCreate(View):
    """The creation form, and the creation itself."""

    def get(self, request):
        return render(request, TEMPLATES + 'partials/sensor_form.html', {'form': SensorForm()})

    def post(self, request):
        form = SensorForm(request.POST, request.FILES)
        # Invalid input: the form goes back to its own container instead of the card grid.
        if not form.is_valid():
            logger.warning("La création d'un capteur a été refusée")
            response = render(request, TEMPLATES + 'partials/sensor_form.html', {'form': form})
            response['HX-Retarget'] = '#sensor-create'
            response['HX-Reswap'] = 'innerHTML'
            return response
        sensor = form.save()
        logger.info("Le capteur " + sensor.name + " a été créé")
        return render(request, TEMPLATES + 'partials/sensor_created.html', {'sensor': sensor})


class SensorDelete(View):
    """
    Removes a sensor from the application. The row is kept, flagged as deleted.

    Nothing is swapped in place: the answer asks the page to load its grid again.
    """

    def post(self, request, sensor_id):
        sensor = get_object_or_404(Sensor, pk=sensor_id, is_deleted=False)
        sensor.is_deleted = True
        sensor.save()
        # Nobody is going to change the batteries of a sensor that is gone.
        feedback.dismiss(sensor)
        logger.info("Le capteur " + sensor.name + " a été supprimé")
        response = HttpResponse(status=204)
        response['HX-Trigger'] = REFRESH_EVENT
        return response
