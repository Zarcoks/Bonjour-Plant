from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views import View

from core.app import app
from mqtt_worker import feedback
from mqtt_worker.feedback import WARNING_KINDS
from mqtt_worker.tasks import switch_the_plugs
from plant_management.models import ACT_ON_HUMIDITY, ACT_ON_LUMINOSITY, Actionner

from .forms import ActionnerForm

logger = app.module_logger("actionners")

# Where the templates of this page live.
TEMPLATES = 'plant_management/actionners/'

# The event asking the page to load its grid again.
REFRESH_EVENT = 'refresh-actionners'


def actionners():
    """The actionners the page shows: never the deleted ones."""
    return Actionner.objects.filter(is_deleted=False).select_related('plant')


def card(request, actionner):
    return render(request, TEMPLATES + 'partials/actionner_card.html', {'actionner': actionner})


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
        return card(request, get_object_or_404(Actionner, pk=actionner_id, is_deleted=False))


class ActionnerDetail(View):
    """The expanded card: every field of the actionner, editable in place."""

    def get(self, request, actionner_id):
        actionner = get_object_or_404(Actionner, pk=actionner_id, is_deleted=False)
        return render(request, TEMPLATES + 'partials/actionner_detail.html',
                      {'actionner': actionner, 'form': ActionnerForm(instance=actionner)})

    def post(self, request, actionner_id):
        actionner = get_object_or_404(Actionner, pk=actionner_id, is_deleted=False)
        form = ActionnerForm(request.POST, request.FILES, instance=actionner)
        # Invalid input: send the edition form back, so the user keeps their changes.
        if not form.is_valid():
            logger.warning("La modification de l'actionneur " + actionner.name + " a été refusée")
            return render(request, TEMPLATES + 'partials/actionner_detail.html',
                          {'actionner': actionner, 'form': form})
        actionner = form.save()
        logger.info("L'actionneur " + actionner.name + " a été modifié, assigné à "
                    + (actionner.plant.display_name if actionner.plant else "aucune plante"))
        return card(request, actionner)


class ActionnerSwitch(View):
    """
    Turns an actionner on and off, from its card, without editing it.

    The order leaves for the plug straight away rather than at the next pass of
    the MQTT worker: a button that takes a minute to be followed reads as a
    button that did nothing.
    """

    def post(self, request, actionner_id):
        actionner = get_object_or_404(Actionner, pk=actionner_id, is_deleted=False)
        actionner.is_on = not actionner.is_on
        actionner.last_switch = timezone.now()
        actionner.save(update_fields=['is_on', 'last_switch'])
        logger.info("L'utilisateur veut " + ("allumer" if actionner.is_on else "éteindre")
                    + " l'actionneur " + actionner.name)
        # Touching the switch by hand is taking that factor of the plant over.
        hand_back_the_watering(actionner)
        if not actionner.is_on:
            hand_back_the_light(actionner)
        switch_the_plugs()
        return card(request, actionner)


def hand_back_the_light(actionner):
    """
    Takes the plant off automatic light when its lamp is switched off by hand.

    Without this, the decision worker would light it again within the minute and
    the switch would look broken: turning a lamp off by hand is taking the light
    of that plant over.
    """
    plant = actionner.plant
    if actionner.act_on != ACT_ON_LUMINOSITY or plant is None or not plant.auto_luminosity:
        return False
    plant.auto_luminosity = False
    plant.save(update_fields=['auto_luminosity'])
    logger.info("La lumière automatique de la plante " + plant.display_name
                + " a été désactivée : l'utilisateur a éteint " + actionner.name)
    return True


def hand_back_the_watering(actionner):
    """
    Takes the plant off automatic watering when its pump is switched by hand.

    Touching the switch of a pump, either way, is taking the water of that plant
    over: the application stops watering it on its own until it is told to again.
    """
    plant = actionner.plant
    if actionner.act_on != ACT_ON_HUMIDITY or plant is None or not plant.auto_watering:
        return False
    plant.auto_watering = False
    plant.save(update_fields=['auto_watering'])
    logger.info("L'arrosage automatique de la plante " + plant.display_name
                + " a été désactivé : l'utilisateur a basculé " + actionner.name)
    return True


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
        # Nobody is going to settle the warnings of a plug that is gone.
        feedback.dismiss(actionner.pk)
        logger.info("L'actionneur " + actionner.name + " a été supprimé")
        response = HttpResponse(status=204)
        response['HX-Trigger'] = REFRESH_EVENT
        return response


def warnings_banner(request):
    """The warnings standing, as the main page shows them."""
    return render(request, TEMPLATES + 'partials/warnings.html',
                  {'warnings': feedback.standing()})


class ActionnerWarnings(View):
    """
    What the plugs belie, asked for again every few seconds by the main page.

    The answer comes from the cache the MQTT worker writes to, not from the
    worker itself.
    """

    def get(self, request):
        return warnings_banner(request)


class DismissActionnerWarning(View):
    """« C'est réglé » : the user takes one warning away, and that one only."""

    def post(self, request, actionner_id, kind):
        actionner = get_object_or_404(Actionner, pk=actionner_id, is_deleted=False)
        if kind not in WARNING_KINDS:
            raise Http404("Cet avertissement n'existe pas")
        feedback.dismiss(actionner.pk, kind)
        logger.info("L'écart de l'actionneur " + actionner.name
                    + " a été réglé par l'utilisateur")
        # The whole banner comes back: settling one warning leaves the others.
        return warnings_banner(request)
