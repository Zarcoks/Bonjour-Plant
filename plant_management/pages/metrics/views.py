import datetime

from django.shortcuts import render
from django.views import View

from plant_management.models import SensorData
from sync_worker import read_measures

from .forms import PlantPickerForm

# Where the templates of this page live.
TEMPLATES = 'plant_management/metrics/'

# How far back the curves go, and how many measures they hold at most.
METRICS_DAYS = 7
METRICS_MAX_POINTS = 500

# How many lines the table under the curves shows.
TABLE_ROWS = 50

# One curve per measure. The colours were validated for colour blindness and for
# their contrast on white; the labels carry the unit.
CURVES = [
    {'field': 'current_humidity', 'title': "Humidité", 'unit': "%", 'colour': '#0369A1'},
    {'field': 'current_luminosity', 'title': "Intensité lumineuse", 'unit': "%", 'colour': '#A16207'},
    {'field': 'current_temperature', 'title': "Température", 'unit': "°C", 'colour': '#BE185D'},
]


def measures_over_time(plant):
    """
    What the sensors of a plant measured lately, in time order.

    Each payload is read with the keys of the sensor that sent it, so two
    sensors naming their measures differently both land on the same curves.
    """
    since = datetime.datetime.now() - datetime.timedelta(days=METRICS_DAYS)
    latest = (SensorData.objects.filter(plant=plant, time__gte=since)
              .select_related('sensor').order_by('-time')[:METRICS_MAX_POINTS])

    curves = {curve['field']: [] for curve in CURVES}
    moments = []
    for data in reversed(list(latest)):
        measures = read_measures(data.sensor, data.payload)
        if not measures:
            continue
        moments.append({'time': data.time, 'measures': measures})
        for field, value in measures.items():
            curves[field].append({'x': data.time.isoformat(timespec='seconds'), 'y': value})
    return curves, moments


def panel(plant):
    """Everything the page shows about one plant."""
    if plant is None:
        return {'plant': None, 'curves': [], 'moments': []}
    curves, moments = measures_over_time(plant)
    return {
        'plant': plant,
        'curves': [dict(curve, points=curves[curve['field']]) for curve in CURVES],
        'moments': list(reversed(moments))[:TABLE_ROWS],
        'days': METRICS_DAYS,
    }


class Metrics(View):
    """
    The measures of one plant over time: its state, then one curve per measure.

    Answers the panel alone to an HTMX request, so that changing plant does not
    reload the whole page.
    """

    def get(self, request):
        form = PlantPickerForm(request.GET)
        context = dict(panel(form.chosen()), form=form, curve_fields=CURVES)
        if request.headers.get('HX-Request'):
            return render(request, TEMPLATES + 'partials/metrics_panel.html', context)
        return render(request, TEMPLATES + 'metrics.html', context)
