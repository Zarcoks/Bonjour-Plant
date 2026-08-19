from django.shortcuts import get_object_or_404, render
from django.views import View

from core.app import app
from plant_management.models import PlantType

from .forms import PlantTypeForm

logger = app.module_logger("plant_types")

# Where the templates of this page live.
TEMPLATES = 'plant_management/plant_types/'


class PlantTypeList(View):
    """Full page: every plant type known by the application, as a grid of cards."""

    def get(self, request):
        plant_types = PlantType.objects.all()
        return render(request, TEMPLATES + 'plant_types.html', {'plant_types': plant_types})


class PlantTypeCard(View):
    """The collapsed card of a plant type (also used to cancel an edition)."""

    def get(self, request, plant_type_id):
        plant_type = get_object_or_404(PlantType, pk=plant_type_id)
        return render(request, TEMPLATES + 'partials/plant_type_card.html', {'plant_type': plant_type})


class PlantTypeDetail(View):
    """The expanded card: every field of the plant type, editable in place."""

    def get(self, request, plant_type_id):
        plant_type = get_object_or_404(PlantType, pk=plant_type_id)
        return render(request, TEMPLATES + 'partials/plant_type_detail.html',
                      {'plant_type': plant_type, 'form': PlantTypeForm(instance=plant_type)})

    def post(self, request, plant_type_id):
        plant_type = get_object_or_404(PlantType, pk=plant_type_id)
        form = PlantTypeForm(request.POST, request.FILES, instance=plant_type)
        # Invalid input: send the edition form back, so the user keeps their changes.
        if not form.is_valid():
            logger.warning("La modification du type de plante " + plant_type.plant_name + " a été refusée")
            return render(request, TEMPLATES + 'partials/plant_type_detail.html',
                          {'plant_type': plant_type, 'form': form})
        plant_type = form.save()
        logger.info("Le type de plante " + plant_type.plant_name + " a été modifié")
        return render(request, TEMPLATES + 'partials/plant_type_card.html', {'plant_type': plant_type})


class PlantTypeCreate(View):
    """The creation form, and the creation itself."""

    def get(self, request):
        return render(request, TEMPLATES + 'partials/plant_type_form.html', {'form': PlantTypeForm()})

    def post(self, request):
        form = PlantTypeForm(request.POST, request.FILES)
        # Invalid input: the form goes back to its own container instead of the card grid.
        if not form.is_valid():
            logger.warning("La création d'un type de plante a été refusée")
            response = render(request, TEMPLATES + 'partials/plant_type_form.html', {'form': form})
            response['HX-Retarget'] = '#plant-type-create'
            response['HX-Reswap'] = 'innerHTML'
            return response
        plant_type = form.save()
        logger.info("Le type de plante " + plant_type.plant_name + " a été créé")
        return render(request, TEMPLATES + 'partials/plant_type_created.html', {'plant_type': plant_type})
