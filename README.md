# Bonjour Plant

Une application Django qui assiste l'entretien des plantes, pour le rendre
simple comme bonjour.

## Structure

- `core/` : configuration du projet (settings, urls, wsgi/asgi) et `app.py`,
  l'objet application
- `Logging/` : l'objet loggueur de l'application
- `static/` : fichiers statiques généraux (design system `bonjour-plant.css`,
  Bootstrap, Bootstrap Icons, HTMX, illustration par défaut)
- `plant_management/` : app métier
  - `models.py` : `PlantType`, `GrowingPlant`, `AppLog`
  - `pages/<page>/` : un dossier par page, contenant ses `views.py`, `urls.py`
    et son `forms.py`
  - `templates/plant_management/<page>/` : les templates de la page, ses
    fragments HTMX dans `partials/`
  - `templates/plant_management/index.html` : la mise en page commune
  - `management/commands/data_setup.py` : crée les types de plantes connus par défaut
- `media/` : photos envoyées par l'utilisateur (hors dépôt)
- `tests/` : tests d'intégration pytest, un module par page

## Lancer en local

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py data_setup
python manage.py runserver
```

Les réglages se surchargent par variables d'environnement, voir `.env.example`.

## Les logs

L'application expose ses services partagés sur un objet application unique, et
le loggueur en fait partie :

```python
from core.app import app

app.logger.info("ma log")
app.logger.warning("la sonde ne répond pas", room="salon")   # -> "... room=salon"
```

Une page peut se donner un loggueur portant son nom, ce qui préfixe la sortie
console (`[INFO] [bonjour_plant.plant_types] ...`) :

```python
logger = app.module_logger("plant_types")
```

Chaque appel écrit une ligne sur la console *et* une ligne dans la table
`app_log`, consultable sur la page Journal. Les niveaux sont `DEBUG`, `INFO`,
`WARNING` et `ERROR` ; la console se limite à `DJANGO_LOGLEVEL`, la base garde
tout. Une écriture en base qui échoue n'interrompt jamais l'appelant.

## Pages et endpoints

| URL | Nom | Rôle |
| --- | --- | --- |
| `/` | `plant_management_index` | page d'accueil |
| `/plant-types/` | `plant_types` | la grille des types de plantes |
| `/plant-types/create/` | `create_plant_type` | GET : formulaire de création, POST : création |
| `/plant-types/<id>/` | `plant_type_detail` | GET : carte dépliée et modifiable, POST : enregistrement |
| `/plant-types/<id>/card/` | `plant_type_card` | carte repliée (sert aussi de « Annuler ») |
| `/logs/` | `logs` | le journal de l'application, filtrable |

Les endpoints de `plant-types` renvoient des fragments HTML destinés à HTMX :
la page n'est jamais rechargée. La création répond avec la nouvelle carte, plus
deux swaps *out of band* qui referment le formulaire et retirent l'état vide. En
cas de saisie invalide, la création est redirigée vers son formulaire via les
en-têtes `HX-Retarget` / `HX-Reswap`.

`/logs/` sert la page complète, ou le tableau seul quand la requête porte
l'en-tête `HX-Request` : filtrer ne recharge donc que le tableau, et l'URL
filtrée reste partageable.

## Tests

```
pytest
```
