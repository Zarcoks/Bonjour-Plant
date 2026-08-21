from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from core.app import app
from plant_management.models import Actionner

from .forms import ActionnerForm

logger = app.module_logger("actionners")

# Where the templates of this page live.
TEMPLATES = 'plant_management/actionners/'

# The event asking the page to load its grid again.
REFRESH_EVENT = 'refresh-actionners'


def actionners():
    """The actionners the page shows: never the deleted ones."""
    return Actionner.objects.filter(is_deleted=False).select_related('plant')


class ActionnerList(View):
    """
    Full page: every actionner of the installation, as a grid of cards.

    Answers the grid alone to an HTMX request, which is how the page loads its
    actionners again after a deletion.
    """

    def get(self, request):
        context = {'actionners': actionners()}
        if request.headers.get('HX-Request'):
            return render(request, TEMPLATES + 'partials/actionners_grid.html', context)
        return render(request, TEMPLATES + 'actionners.html', context)


class ActionnerCard(View):
    """The collapsed card of an actionner (also used to cancel an edition)."""

    def get(self, request, actionner_id):
        actionner = get_object_or_404(Actionner, pk=actionner_id, is_deleted=False)
        return render(request, TEMPLATES + 'partials/actionner_card.html', {'actionner': actionner})


class ActionnerDetail(View):
    """The expanded card: every field of the actionner, editable in place."""

    def get(self, request, actionner_id):
        actionner = get_object_or_404(Actionner, pk=actionner_id, is_deleted=False)
        return render(request, TEMPLATES + 'partials/actionner_detail.html',
                      {'actionner': actionner, 'form': ActionnerForm(instance=actionner)})

    def post(self, request, actionner_id):
        actionner = get_object_or_404(Actionner, pk=actionner_id, is_deleted=False)
        was_on = actionner.is_on
        form = ActionnerForm(request.POST, request.FILES, instance=actionner)
        # Invalid input: send the edition form back, so the user keeps their changes.
        if not form.is_valid():
            logger.warning("La modification de l'actionneur " + actionner.name + " a été refusée")
            return render(request, TEMPLATES + 'partials/actionner_detail.html',
                          {'actionner': actionner, 'form': form})
        actionner = form.save()
        logger.info("L'actionneur " + actionner.name + " a été modifié, assigné à "
                    + (actionner.plant.display_name if actionner.plant else "aucune plante"))
        if actionner.is_on != was_on:
            logger.info("L'actionneur " + actionner.name + " a été "
                        + ("allumé" if actionner.is_on else "éteint"))
        return render(request, TEMPLATES + 'partials/actionner_card.html', {'actionner': actionner})


class ActionnerCreate(View):
    """The creation form, and the creation itself."""

    def get(self, request):
        return render(request, TEMPLATES + 'partials/actionner_form.html', {'form': ActionnerForm()})

    def post(self, request):
        form = ActionnerForm(request.POST, request.FILES)
        # Invalid input: the form goes back to its own container instead of the card grid.
        if not form.is_valid():
            logger.warning("La création d'un actionneur a été refusée")
            response = render(request, TEMPLATES + 'partials/actionner_form.html', {'form': form})
            response['HX-Retarget'] = '#actionner-create'
            response['HX-Reswap'] = 'innerHTML'
            return response
        actionner = form.save()
        logger.info("L'actionneur " + actionner.name + " a été créé")
        return render(request, TEMPLATES + 'partials/actionner_created.html', {'actionner': actionner})


class ActionnerDelete(View):
    """
    Removes an actionner from the application. The row is kept, flagged as deleted.

    Nothing is swapped in place: the answer asks the page to load its grid again.
    """

    def post(self, request, actionner_id):
        actionner = get_object_or_404(Actionner, pk=actionner_id, is_deleted=False)
        actionner.is_deleted = True
        actionner.save()
        logger.info("L'actionneur " + actionner.name + " a été supprimé")
        response = HttpResponse(status=204)
        response['HX-Trigger'] = REFRESH_EVENT
        return response
