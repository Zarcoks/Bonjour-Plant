from django.views import View
from django.shortcuts import render

from mqtt_worker import state
from plant_management.models import AppLog

from .forms import LogFilterForm

# Where the templates of this page live.
TEMPLATES = 'plant_management/logs/'

# The log page shows the latest records only, however far the user scrolls.
LOGS_SHOWN = 200


class MqttTopics(View):
    """
    What the MQTT worker listens to, right now.

    The page asks again every few seconds: the answer comes from the cache the
    worker writes to, not from the worker itself.
    """

    def get(self, request):
        return render(request, TEMPLATES + 'partials/mqtt_topics.html',
                      {'subscriptions': state.read()})


class LogList(View):
    """
    The application log, newest first, narrowed down by the filters.

    Answers the table alone to an HTMX request, so that filtering does not
    reload the whole page.
    """

    def get(self, request):
        form = LogFilterForm(request.GET)
        # Newest first: the id breaks the ties between records of the same second.
        logs = form.filter(AppLog.objects.order_by('-time', '-id'))[:LOGS_SHOWN]
        context = {'logs': logs, 'form': form, 'logs_shown': LOGS_SHOWN,
                   'subscriptions': state.read()}
        if request.headers.get('HX-Request'):
            return render(request, TEMPLATES + 'partials/logs_table.html', context)
        return render(request, TEMPLATES + 'logs.html', context)
