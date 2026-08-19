from django.views import View
from django.shortcuts import render

from plant_management.models import AppLog

from .forms import LogFilterForm

# Where the templates of this page live.
TEMPLATES = 'plant_management/logs/'

# The log page shows the latest records only, however far the user scrolls.
LOGS_SHOWN = 200


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
        context = {'logs': logs, 'form': form, 'logs_shown': LOGS_SHOWN}
        if request.headers.get('HX-Request'):
            return render(request, TEMPLATES + 'partials/logs_table.html', context)
        return render(request, TEMPLATES + 'logs.html', context)
