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
- `Dockerfile`, `entrypoint.sh`, `Caddyfile`, `docker-compose.yaml` : le déploiement

## Déployer avec Docker

Toute la stack se déploie sur le port 80, en HTTP :

```
cp .env.example .env      # puis renseigner DJANGO_SECRET_KEY, DATABASE_PASSWORD et DJANGO_ALLOWED_HOSTS
docker compose up -d --build
```

L'application est alors prête à l'emploi sur http://localhost/ : `entrypoint.sh`
attend PostgreSQL, applique les migrations, collecte les fichiers statiques,
installe les types de plantes par défaut, puis lance gunicorn.

Trois services :

| Service | Rôle |
| --- | --- |
| `caddy` | publie le port 80, sert `/static/` et `/media/`, proxifie le reste vers gunicorn |
| `django-web` | l'application derrière gunicorn (4 workers), sur le port 8000 interne |
| `db` | PostgreSQL 17 |

Les données survivent aux redéploiements dans trois volumes nommés :
`postgres_data`, `media_data` (les photos envoyées) et `static_data` (les
fichiers collectés).

```
docker compose logs -f django-web    # suivre les logs de l'application
docker compose down                  # arrêter, en gardant les données
docker compose down -v               # arrêter et tout effacer
```

## Lancer en local, sans Docker

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py data_setup
python manage.py runserver
```

Les réglages se surchargent par variables d'environnement, voir `.env.example`.
En local, sans variable d'environnement, l'application tourne en SQLite avec
`DEBUG` actif ; le `.env` n'est lu que par Docker Compose.

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
| `/` | `growing_plants` | les plantes en cours de croissance, une carte par ligne |
| `/plants/create/` | `create_growing_plant` | GET : formulaire de création, POST : création |
| `/plants/<id>/` | `growing_plant_detail` | GET : carte modifiable, POST : enregistrement |
| `/plants/<id>/card/` | `growing_plant_card` | carte en lecture (sert aussi de « Annuler ») |
| `/plants/<id>/delete/` | `delete_growing_plant` | POST : suppression, après confirmation |
| `/plants/<id>/auto-luminosity/` | `growing_plant_auto_luminosity` | POST : bascule la lumière automatique |
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
filtrée reste partageable. `/` suit la même règle pour l'interrupteur des
plantes récoltées (`?harvested=1`).

## Les signes des cartes de plantes

Chaque carte porte, sur la photo, ce que les dernières mesures disent de la
plante face à ce que son type demande. Les SVG sont dans
`growing_plants/partials/growing_plant_signs.html`, la comparaison dans les
méthodes du modèle `GrowingPlant`.

| Signe | Quand |
| --- | --- |
| soleil | `current_luminosity` ≥ `luminosity_per_day` |
| nuage | `current_luminosity` < `luminosity_per_day` |
| thermomètre | `current_temperature` > `temperature_max` |
| flocon | `current_temperature` < `temperature_min` |
| goutte d'eau | `current_humidity` < `humidity_min` |

Une mesure absente n'affiche aucun signe, et une plante récoltée n'en affiche
aucun non plus.

## Les plantes de la page principale

Les plantes sont triées par date de plantation, les récoltées à la fin, et les
supprimées ne sont jamais listées.

Une plante **récoltée** ne garde que son nom, sa photo, sa date de plantation et
sa barre de croissance, avec la mention « Récoltée » et le jour de récolte
(`harvest_day`). Cocher la case « Récoltée » note le jour même si aucun n'est
choisi ; décocher la case efface le jour.

La **suppression** est douce : la ligne reste en base, marquée `is_deleted`. Le
bouton demande confirmation (`hx-confirm`), puis la réponse ne remplace rien :
elle renvoie l'en-tête `HX-Trigger: refresh-plants`, sur lequel la page recharge
sa liste — ce qui garde le filtre et l'ordre justes. La **création** répond avec
la liste entière, pour que la nouvelle plante se place à sa date.

## Tests

```
pytest
```
