# Bonjour Plant

Une application Django qui assiste l'entretien des plantes, pour le rendre
simple comme bonjour.

## Structure

- `core/` : configuration du projet (settings, urls, wsgi/asgi) et `app.py`,
  l'objet application
- `Logging/` : l'objet loggueur de l'application
- `mqtt_worker/` : le worker qui écoute les capteurs sur le broker MQTT
- `sync_worker/` : le worker qui recopie les mesures reçues sur les plantes
- `static/` : fichiers statiques généraux (design system `bonjour-plant.css`,
  Bootstrap, Bootstrap Icons, HTMX, illustration par défaut)
- `plant_management/` : app métier
  - `models.py` : `PlantType`, `GrowingPlant`, `Sensor`, `SensorData`, `AppLog`
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
| `django-web` | l'application derrière gunicorn, sur le port 8000 interne |
| `celery` | les deux workers : l'écoute MQTT et la synchronisation périodique |
| `redis` | le courtier de messages de Celery |
| `mqtt` | un broker Mosquitto de développement, sur le port 1883 |
| `db` | PostgreSQL 17 |

Les données survivent aux redéploiements dans trois volumes nommés :
`postgres_data`, `media_data` (les photos envoyées) et `static_data` (les
fichiers collectés).

```
docker compose logs -f django-web    # suivre les logs de l'application
docker compose down                  # arrêter, en gardant les données
docker compose down -v               # arrêter et tout effacer
```

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
En local, sans variable d'environnement, l'application tourne en SQLite avec
`DEBUG` actif ; le `.env` n'est lu que par Docker Compose.

### Avec les capteurs

`runserver` seul ne fait pas tourner le worker. Dans un second terminal :

```
python manage.py dev_services
```

La commande démarre ce qui manque — un Redis sur le port 6379, un broker
Mosquitto sur le port 1883 — puis lance le worker Celery au premier plan, lequel
se met à écouter les capteurs tout seul. Un service qui répond déjà sur son port
est réutilisé tel quel, qu'il vienne d'une installation locale ou de la stack
Docker. Ctrl-C arrête le worker et les conteneurs que la commande avait démarrés,
sans toucher à ceux qu'elle a réutilisés.

Le worker et `runserver` partagent alors le même fichier SQLite : les écritures
sont sérialisées, ce qui suffit largement en développement.

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
`app_log`, consultable sur la page Journal — il n'existe pas de journalisation
qui ne passerait pas par la base. Les niveaux sont `DEBUG`, `INFO`, `WARNING` et
`ERROR` ; la console se limite à `DJANGO_LOGLEVEL`, la base garde tout. Une
écriture en base qui échoue n'interrompt jamais l'appelant.

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
| `/sensors/` | `sensors` | la grille des capteurs |
| `/sensors/create/` | `create_sensor` | GET : formulaire de création, POST : création |
| `/sensors/<id>/` | `sensor_detail` | GET : carte dépliée et modifiable, POST : enregistrement |
| `/sensors/<id>/card/` | `sensor_card` | carte repliée (sert aussi de « Annuler ») |
| `/sensors/<id>/delete/` | `delete_sensor` | POST : suppression, après confirmation |
| `/logs/` | `logs` | le journal de l'application, filtrable |

Les endpoints de `plant-types` renvoient des fragments HTML destinés à HTMX :
la page n'est jamais rechargée. La création répond avec la nouvelle carte, plus
deux swaps *out of band* qui referment le formulaire et retirent l'état vide. En
cas de saisie invalide, la création est redirigée vers son formulaire via les
en-têtes `HX-Retarget` / `HX-Reswap`.

`/logs/` sert la page complète, ou le tableau seul quand la requête porte
l'en-tête `HX-Request` : filtrer ne recharge donc que le tableau, et l'URL
filtrée reste partageable. Le tableau garde une hauteur bornée et défile sur
lui-même, en-tête figé ; il ne contient jamais plus de `LOGS_SHOWN` (200) logs,
de la plus récente à la plus ancienne. `/` suit la même règle pour l'interrupteur des
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

## Les capteurs

Un capteur existe indépendamment des plantes : il est assigné à l'une d'elles ou
à aucune. Sa page reprend le CRUD des types de plantes — grille de cartes, carte
dépliée modifiable, photo par défaut, création en HTMX — avec en plus le champ
« Assigner à » et la suppression.

Comme pour les plantes, la suppression est douce (`is_deleted`), demande
confirmation, et la réponse renvoie `HX-Trigger: refresh-sensors` sur lequel la
grille se recharge. Supprimer une plante libère les capteurs qui la suivaient.

### Les clés du payload

Deux capteurs ne nomment pas forcément leurs mesures pareil dans le JSON qu'ils
publient. Chaque capteur porte donc trois champs texte, modifiables dans son
interface : `humidity_payload_label`, `luminosity_payload_label` et
`temperature_payload_label`. Ils valent `humidity`, `luminosity` et
`temperature` par défaut ; un champ laissé vide reprend cette valeur à
l'enregistrement, et les méthodes `get_*_label()` du modèle assurent le même
repli pour une ligne écrite hors de l'interface.

## Le worker MQTT

Le paquet `mqtt_worker/` écoute les capteurs. L'adresse du broker vient de
`MQTT_BROKER_URL` dans le `.env` (`mqtt://`, `mqtts://`, avec identifiants
éventuels), les topics viennent du champ `mqtt_topic` des capteurs.

Le worker démarre **tout seul** : le signal Celery `worker_ready` met la tâche
`mqtt_worker.listen_to_sensors` en file dès que le worker est prêt, sans rien à
lancer à la main. La tâche garde la connexion aussi longtemps que le worker
vit ; si elle tombe, elle est remise en file.

Toutes les `MQTT_SYNC_SECONDS` (30 s par défaut), le worker relit la table des
capteurs et met ses abonnements à jour : un capteur ajouté est écouté, un
capteur supprimé ou dont le topic change voit son ancien topic abandonné. Une
reconnexion au broker reprend tous les abonnements, puisqu'une nouvelle session
MQTT n'en porte aucun.

À l'arrivée d'un message, une ligne `sensor_data` est écrite par capteur assigné
qui écoute ce topic. **Une donnée venant d'un capteur assigné à aucune plante
est abandonnée**, comme celle d'un topic que plus aucun capteur ne réclame. Les
topics à jokers (`bonjour-plant/+/humidity`) sont gérés.

Les événements du worker — connexion, abonnements, déconnexions, erreurs — sont
journalisés dans la base comme le reste de l'application. Les lignes de trafic
par mesure sont, elles, laissées en commentaire dans `handle_message` : une ligne
d'`app_log` par mesure noierait tout le reste du journal. Il suffit de les
décommenter pour suivre le détail.

Pour écouter sans passer par Celery, en local :

```
python manage.py listen_sensors
```

## Le worker de synchronisation

Le paquet `sync_worker/` recopie les mesures reçues sur les plantes. La tâche
`sync_worker.sync_sensors_to_plants` tourne toutes les `PLANT_SYNC_SECONDS`
(30 s par défaut), portée par l'ordonnanceur embarqué du worker Celery
(`celery -A core worker --beat`).

Pour chaque plante non supprimée, elle prend la **dernière** donnée de chacun de
ses capteurs, lit le payload avec les clés de ce capteur, et écrit
`current_humidity`, `current_luminosity` et `current_temperature`. Quand deux
capteurs donnent la même mesure, la donnée la plus récente gagne. Les valeurs
sont converties à ce que le modèle attend : humidité et luminosité arrondies,
température en flottant.

Rien n'est écrit quand rien n'a bougé, et seuls les champs modifiés sont
enregistrés. Un passage qui se déroule bien ne journalise rien ; seuls les
payloads illisibles produisent un avertissement, groupé par passage. Une clé absente du payload laisse la mesure correspondante
inchangée ; un payload qui n'est pas un objet JSON est ignoré.

## Tests

```
pytest
```
