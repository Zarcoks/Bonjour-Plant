from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from core.app import app
from plant_management.models import GrowingPlant

from .forms import GrowingPlantCreateForm, GrowingPlantForm

logger = app.module_logger("growing_plants")

# Where the templates of this page live.
TEMPLATES = 'plant_management/growing_plants/'

# The event asking the page to load its list again.
REFRESH_EVENT = 'refresh-plants'


def growing_plants(show_harvested):
    """
    The plants the page shows: never the deleted ones, the harvested ones on
    demand. Sorted by planting date, the harvested ones at the end.
    """
    plants = GrowingPlant.objects.filter(is_deleted=False).select_related('plant_type')
    if not show_harvested:
        plants = plants.filter(harvested=False)
    return plants.order_by('harvested', F('planted_date').asc(nulls_last=True))


def asks_for_harvested(request):
    """Whether the page currently shows the harvested plants too."""
    return request.GET.get('harvested') == '1' or request.POST.get('harvested') == '1'


def card(request, plant):
    return render(request, TEMPLATES + 'partials/growing_plant_card.html', {'plant': plant})


class GrowingPlantList(View):
    """
    Main page: the plants being grown, one card per row.

    Answers the list alone to an HTMX request, so that toggling the harvested
    plants does not reload the whole page.
    """

    def get(self, request):
        show_harvested = asks_for_harvested(request)
        context = {'plants': growing_plants(show_harvested), 'show_harvested': show_harvested}
        if request.headers.get('HX-Request'):
            return render(request, TEMPLATES + 'partials/growing_plants_list.html', context)
        return render(request, TEMPLATES + 'growing_plants.html', context)


class GrowingPlantCard(View):
    """The card of a plant as it is read (also used to cancel an edition)."""

    def get(self, request, plant_id):
        return card(request, get_object_or_404(GrowingPlant, pk=plant_id, is_deleted=False))


class GrowingPlantDetail(View):
    """The same card, with its editable fields."""

    def get(self, request, plant_id):
        plant = get_object_or_404(GrowingPlant, pk=plant_id, is_deleted=False)
        return render(request, TEMPLATES + 'partials/growing_plant_detail.html',
                      {'plant': plant, 'form': GrowingPlantForm(instance=plant)})

    def post(self, request, plant_id):
        plant = get_object_or_404(GrowingPlant, pk=plant_id, is_deleted=False)
        # Read before validating: the form writes the submitted data on the instance.
        was_harvested = plant.harvested
        form = GrowingPlantForm(request.POST, instance=plant)
        # Invalid input: send the edition form back, so the user keeps their changes.
        if not form.is_valid():
            logger.warning("La modification de la plante " + plant.display_name + " a été refusée")
            return render(request, TEMPLATES + 'partials/growing_plant_detail.html',
                          {'plant': plant, 'form': form})
        plant = form.save()
        logger.info("La plante " + plant.display_name + " a été modifiée")
        if plant.harvested and not was_harvested:
            logger.info("La plante " + plant.display_name + " a été récoltée")
        return card(request, plant)


class GrowingPlantCreate(View):
    """The creation form, and the creation itself."""

    def get(self, request):
        return render(request, TEMPLATES + 'partials/growing_plant_form.html', {'form': GrowingPlantCreateForm()})

    def post(self, request):
        form = GrowingPlantCreateForm(request.POST)
        # Invalid input: the form goes back to its own container instead of the list.
        if not form.is_valid():
            logger.warning("La création d'une plante a été refusée")
            response = render(request, TEMPLATES + 'partials/growing_plant_form.html', {'form': form})
            response['HX-Retarget'] = '#growing-plant-create'
            response['HX-Reswap'] = 'innerHTML'
            return response
        plant = form.save()
        logger.info("La plante " + plant.display_name + " a été plantée")
        # The whole list comes back, so that the new plant lands at its place in the order.
        show_harvested = asks_for_harvested(request)
        return render(request, TEMPLATES + 'partials/growing_plant_created.html',
                      {'plants': growing_plants(show_harvested), 'show_harvested': show_harvested})


class GrowingPlantDelete(View):
    """
    Removes a plant from the application. The row is kept, flagged as deleted.

    Nothing is swapped in place: the answer asks the page to load its list
    again, which keeps both the harvested filter and the order right.
    """

    def post(self, request, plant_id):
        plant = get_object_or_404(GrowingPlant, pk=plant_id, is_deleted=False)
        plant.is_deleted = True
        plant.save()
        # Its sensors go back to the free ones.
        freed = plant.sensors.update(plant=None)
        logger.info("La plante " + plant.display_name + " a été supprimée, "
                    + str(freed) + " capteur(s) libéré(s)")
        response = HttpResponse(status=204)
        response['HX-Trigger'] = REFRESH_EVENT
        return response


class GrowingPlantAutoLuminosity(View):
    """Turns the automatic light of a plant on and off."""

    def post(self, request, plant_id):
        plant = get_object_or_404(GrowingPlant, pk=plant_id, is_deleted=False)
        plant.auto_luminosity = not plant.auto_luminosity
        plant.save()
        logger.info("La lumière automatique de la plante " + plant.display_name + " a été "
                    + ("activée" if plant.auto_luminosity else "désactivée"))
        return card(request, plant)
