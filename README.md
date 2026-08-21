# Bonjour Plant

Une application Django qui assiste l'entretien des plantes, pour le rendre
simple comme bonjour.

## Structure

- `core/` : configuration du projet (settings, urls, wsgi/asgi) et `app.py`,
  l'objet application
- `Logging/` : l'objet loggueur de l'application
- `mqtt_worker/` : le worker qui écoute les capteurs sur le broker MQTT
- `sync_worker/` : le worker qui recopie les mesures reçues sur les plantes
- `decision_worker/` : le worker qui prend les décisions automatiques
- `coherence_worker/` : le worker qui vérifie que les prises font ce qu'on leur demande
- `static/` : fichiers statiques généraux (design system `bonjour-plant.css`,
  Bootstrap, Bootstrap Icons, HTMX, illustration par défaut)
- `plant_management/` : app métier
  - `models.py` : `PlantType`, `GrowingPlant`, `Sensor`, `SensorData`, `Actionner`, `AppLog`
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
| `celery` | les workers : écoute MQTT, synchronisation, décisions automatiques |
| `redis` | le courtier de messages de Celery, et le cache de l'application |
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
| `/plants/<id>/auto-watering/` | `growing_plant_auto_watering` | POST : bascule l'arrosage automatique |
| `/plant-types/` | `plant_types` | la grille des types de plantes |
| `/plant-types/create/` | `create_plant_type` | GET : formulaire de création, POST : création |
| `/plant-types/<id>/` | `plant_type_detail` | GET : carte dépliée et modifiable, POST : enregistrement |
| `/plant-types/<id>/card/` | `plant_type_card` | carte repliée (sert aussi de « Annuler ») |
| `/metrics/` | `metrics` | les mesures d'une plante dans le temps |
| `/sensors/` | `sensors` | la grille des capteurs |
| `/sensors/create/` | `create_sensor` | GET : formulaire de création, POST : création |
| `/sensors/<id>/` | `sensor_detail` | GET : carte dépliée et modifiable, POST : enregistrement |
| `/sensors/<id>/card/` | `sensor_card` | carte repliée (sert aussi de « Annuler ») |
| `/sensors/<id>/delete/` | `delete_sensor` | POST : suppression, après confirmation |
| `/actionners/` | `actionners` | la grille des actionneurs |
| `/actionners/create/` | `create_actionner` | GET : formulaire de création, POST : création |
| `/actionners/warnings/` | `actionner_warnings` | les prises qui démentent l'application, redemandé en HTMX |
| `/actionners/<id>/warnings/<genre>/dismiss/` | `dismiss_actionner_warning` | POST : « c'est réglé », cet écart-là est retiré |
| `/actionners/<id>/` | `actionner_detail` | GET : carte dépliée et modifiable, POST : enregistrement |
| `/actionners/<id>/card/` | `actionner_card` | carte repliée (sert aussi de « Annuler ») |
| `/actionners/<id>/delete/` | `delete_actionner` | POST : suppression, après confirmation |
| `/logs/` | `logs` | le journal de l'application, filtrable |
| `/logs/topics/` | `mqtt_topics` | les topics MQTT écoutés en ce moment |

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
| soleil | niveau de lumière ≥ `WELL_LIT_LEVEL` (`nor`) |
| nuage | niveau de lumière < `WELL_LIT_LEVEL` |
| thermomètre | `current_temperature` > `temperature_max` |
| flocon | `current_temperature` < `temperature_min` |
| goutte d'eau | `current_humidity` < `humidity_min` |

Une mesure absente n'affiche aucun signe, et une plante récoltée n'en affiche
aucun non plus.

`current_luminosity` est le **niveau** de lumière reçu par la plante. Les
capteurs ne donnent pas un nombre mais l'un de cinq paliers — `low-`, `low`,
`nor`, `high`, `high+` — rangés dans `LUMINOSITY_LEVELS` et stockés par leur
rang, de 0 à 4. L'interface les écrit en mots : très faible, faible, normale,
forte, très forte. Une valeur hors de cette échelle est traitée comme inconnue.

C'est une grandeur différente de la **plage horaire** du type de plante
(`light_starts_at`, `light_ends_at`), qui dit à quelles heures de la journée
l'espèce devrait recevoir de la lumière ; les deux ne se comparent pas, et le
signe soleil/nuage se lit sur le seul niveau.

## Les plantes de la page principale

Les plantes sont triées par date de plantation, les récoltées à la fin, et les
supprimées ne sont jamais listées.

Chaque carte porte les dernières mesures de la plante — humidité, niveau de
lumière, température — dans les couleurs des courbes de la page métriques, pour
qu'un chiffre ici et une courbe là se lisent comme la même mesure. Une mesure
absente s'écrit « — ».

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

## Les actionneurs

Un actionneur est une prise connectée avec un appareil dessus — lampe UV,
humidificateur, tapis chauffant. Sa page reprend le CRUD des capteurs : grille de
cartes, carte dépliée modifiable, photo par défaut, création en HTMX,
suppression après confirmation.

Il porte son nom, sa photo, son état (`is_on`), la plante à laquelle il est
assigné ou non, et le facteur sur lequel il agit (`act_on` : humidité, lumière ou
température, les mêmes noms que les mesures). `last_switch` est daté par le
formulaire, et seulement quand l'état change vraiment : modifier le nom ne compte
pas comme une bascule.

Il porte surtout **deux topics, un par sens** : `mqtt_topic_out`, sur lequel
partent les ordres de bascule, et `mqtt_topic_in`, sur lequel la prise raconte ce
qu'elle est vraiment. Une prise qui ne fait que recevoir des ordres laisse le
second vide. `state_payload_label` dit sous quelle clé son état est écrit dans le
payload — `state` par défaut, la clé de zigbee2mqtt — et cette clé sert dans les
deux sens : on parle à une prise comme elle nous parle. Les trois champs se
modifient depuis la carte dépliée.

Comme pour les capteurs, la suppression est douce (`is_deleted`), demande
confirmation, et la réponse renvoie `HX-Trigger: refresh-actionners` sur lequel
la grille se recharge. Supprimer une plante libère aussi ses actionneurs.

### Commander les prises

`mqtt_worker/switching.py` fait suivre la réalité : toutes les
`ACTIONNER_SYNC_SECONDS` (60 s par défaut), la tâche
`mqtt_worker.switch_the_plugs` envoie à chaque actionneur l'état que la base dit
qu'il devrait avoir, sur son `mqtt_topic_out`. Le format est celui qu'attend une
prise TS011F derrière zigbee2mqtt :

```
bonjour-plant/balcon/lampe/set   {"state": "ON"}
```

L'ordre est renvoyé à chaque passage plutôt qu'aux seuls changements : une prise
basculée à la main, ou qui a perdu le courant et est revenue éteinte, se remet
d'elle-même en accord avec l'application en moins d'une minute. Les ordres
partent par un client MQTT le temps d'une publication, indépendant de celui qui
écoute les capteurs. Un broker injoignable est signalé dans le journal, sans
plus : le passage suivant est à une minute.

Le journal garde les deux versants d'une bascule : ce que l'utilisateur a
demandé (« L'utilisateur veut allumer l'actionneur … », écrit par le formulaire)
et l'instruction partie sur le broker (« Instruction MQTT envoyée … : ON sur
… »). L'instruction n'est écrite que lorsqu'elle change : l'ordre part à chaque
passage, mais une ligne par prise et par minute enterrerait tout le reste du
journal. Le dernier état envoyé est retenu en cache pour cela.

### Ce que la prise raconte d'elle-même

La base reste la référence, mais la prise a maintenant droit à la parole.
`mqtt_worker/feedback.py` lit les messages qui arrivent sur le `mqtt_topic_in`
d'un actionneur, en sort l'état sous la clé de cet actionneur, et le compare à ce
que l'application attend de lui :

```
bonjour-plant/balcon/lampe   {"state": "ON"}   alors que la base la veut éteinte
```

Les prises ne disent pas toutes « ON » et « OFF » : `true`, `1`, `yes`, `off`,
quelle que soit la casse, sont comprises aussi. Un payload illisible, sans la
clé, ou portant autre chose qu'un état **n'est pas un désaccord** — on ne
signale que ce qu'on a su lire.

Un désaccord est déposé dans le cache **sans expiration** : il tient jusqu'à ce
que l'utilisateur appuie sur « C'est réglé » sur la page principale. Une prise
qui se remet d'accord toute seule ne retire donc pas le message — une prise qui
a dérivé mérite d'être vue, même une fois rentrée dans le rang. Le désaccord qui
tient déjà est rafraîchi (dernier état entendu, heure) sans repartir : le
journal garde une ligne `WARNING` par prise qui a dérivé, pas une par message
qu'elle envoie. Supprimer un actionneur retire ses messages.

Une prise peut démentir l'application de deux façons, et les deux tiennent en
même temps : `state`, l'état qu'elle annonce (ci-dessus), et `effect`, l'effet
qu'elle n'a pas (plus bas). Le cache porte donc **une entrée par actionneur et
par genre**, chacune signalée et réglée séparément ; c'est le genre qui voyage
dans l'URL de « C'est réglé ». Chaque avertissement porte la phrase à afficher,
qui suit le nom de la prise sur la page comme dans le journal.

Le bandeau vit en haut de la page « Mes plantes ». Il se redemande tout seul
toutes les 15 secondes, en HTMX, donc une prise qui dérive pendant que la page
est ouverte apparaît sans rechargement ; « C'est réglé » retire une ligne et
renvoie le bandeau, les autres écarts restent. Les écarts sont lus depuis le
cache en partant des actionneurs de la base croisés avec les genres — jamais en
listant le cache lui-même.

## Le worker MQTT

Le paquet `mqtt_worker/` écoute l'installation. L'adresse du broker vient de
`MQTT_BROKER_URL` dans le `.env` (`mqtt://`, `mqtts://`, avec identifiants
éventuels), les topics viennent du champ `mqtt_topic` des capteurs et du
`mqtt_topic_in` des actionneurs qui rapportent leur état.

Le worker démarre **tout seul** : le signal Celery `worker_ready` met la tâche
`mqtt_worker.listen_to_sensors` en file dès que le worker est prêt, sans rien à
lancer à la main. La tâche garde la connexion aussi longtemps que le worker
vit ; si elle tombe, elle est remise en file.

Toutes les `MQTT_SYNC_SECONDS` (30 s par défaut), le worker relit les appareils
et met ses abonnements à jour : un appareil ajouté est écouté, un appareil
supprimé ou dont le topic change voit son ancien topic abandonné. Une
reconnexion au broker reprend tous les abonnements, puisqu'une nouvelle session
MQTT n'en porte aucun.

À l'arrivée d'un message, une ligne `sensor_data` est écrite par capteur assigné
qui écoute ce topic, et le même message est relu pour les actionneurs qui
rapportent sur ce topic. **Une donnée venant d'un capteur assigné à aucune plante
est abandonnée**, comme celle d'un topic que plus aucun capteur ne réclame. Les
topics à jokers (`bonjour-plant/+/humidity`) sont gérés.

Les événements du worker — connexion, abonnements, déconnexions, erreurs — sont
journalisés dans la base comme le reste de l'application. Les lignes de trafic
par mesure sont, elles, laissées en commentaire dans `handle_message` : une ligne
d'`app_log` par mesure noierait tout le reste du journal. Il suffit de les
décommenter pour suivre le détail.

### Ce qui est écouté, en direct

Le worker vit dans un autre processus que le site : il dépose ses abonnements
dans le cache Redis à chaque synchronisation (`mqtt_worker/state.py`), et la page
Journal les lit de là. Le panneau du haut se redemande tout seul toutes les
10 secondes, en HTMX, et affiche le broker, les topics et l'heure de la dernière
publication.

L'entrée ne vit que trois synchronisations : un worker qui s'arrête de parler
cesse d'être annoncé comme à l'écoute, et la page passe à « Le worker n'écoute
pas ». Le worker efface aussi l'entrée quand il se déconnecte ou s'arrête.

### L'arrosage

À chaque mesure reçue, `mqtt_worker/watering.py` compare l'humidité à celle de la
dernière mesure du même capteur prise **au moins trois minutes plus tôt**
(`LOOK_BACK`). Une hausse de plus de `HUMIDITY_RISE` points — 15 par défaut —
signe un arrosage : `last_watering` de la plante prend l'heure de la mesure, et
le journal en garde une ligne.

C'est bien une **hausse** qui est cherchée, et non un écart : une humidité qui
descend est un sol qui sèche, l'inverse d'un arrosage. La comparaison se fait
capteur par capteur et plante par plante, et lit chaque payload avec les clés du
capteur qui l'a envoyé.

### Quand plus personne n'écoute

`worker_ready` ne part qu'au démarrage d'un worker, et le message est acquitté
dès qu'un enfant du pool le prend : un enfant tué emporte l'écoute avec lui, et
rien ne la ramènerait. La tâche `mqtt_worker.watch_the_listening`, planifiée
toutes les `MQTT_WATCH_SECONDS` (60 s par défaut), s'en charge — elle remet
l'écoute en file dès que plus personne ne la tient.

Le « qui la tient » est une réservation en cache prise atomiquement
(`cache.add`), séparée des abonnements : un listener qui démarre, ou qui
réessaie sur un broker muet, tient l'écoute sans avoir encore un seul topic à
montrer. Sans cette distinction, la surveillance empilerait une écoute par
minute pendant une panne de broker, et toutes se réveilleraient ensemble en
enregistrant chaque mesure en double. Personne ne rend jamais la réservation :
elle se perd en n'étant plus rafraîchie, ce qui est exactement ce que fait un
processus tué.

Un Redis injoignable ne casse rien : le cache est configuré en
`IGNORE_EXCEPTIONS`, les pages restent servies, et le panneau dit simplement
qu'il n'a rien à annoncer.

Pour écouter sans passer par Celery, en local :

```
python manage.py listen_sensors
```

## La page métriques

`/metrics/` montre une plante à la fois : l'interrupteur du haut la choisit —
les plantes récoltées y sont proposées, nommées comme telles — puis viennent son
état (photo, nom, type, date de plantation, récolte, mesures actuelles) et trois
courbes, une par mesure. Changer de plante remplace le panneau seul, en HTMX, et
l'URL suit (`?plant=<id>`).

Les séries sont construites en relisant les payloads des sept derniers jours avec
les clés de chaque capteur, donc deux capteurs qui nomment leurs mesures
autrement alimentent les mêmes courbes. La courbe de lumière est tracée en
marches sur ses cinq paliers nommés, les deux autres en lignes. Les courbes sont dessinées par
ApexCharts (`static/apexcharts.min.js`, `static/plant-metrics.js`).

Trois choix de lisibilité : une seule série par graphique, donc pas de légende —
le titre et sa pastille de couleur nomment la courbe ; les couleurs
(`#0369A1`, `#A16207`, `#BE185D`) ont été validées pour le daltonisme et pour
leur contraste sur blanc ; et un tableau dépliable sous les courbes donne les
valeurs sans avoir à survoler quoi que ce soit.

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

Le même passage met à jour **l'avancement de la croissance** : le temps écoulé
depuis la plantation, heure comprise, divisé par les jours que l'espèce met à
être prête (`harvest_days` du type de plante). Contrairement aux mesures, cet
avancement ne doit rien aux capteurs — il suit le calendrier, il est donc
recalculé pour chaque plante à chaque passage. Il est borné à 100 %, et une
plante récoltée garde l'avancement qu'elle avait : sa croissance est finie, et
continuer à compter l'emmènerait au-delà de sa propre récolte.

Rien n'est écrit quand rien n'a bougé, et seuls les champs modifiés sont
enregistrés — mesures et avancement dans une seule écriture. Un passage qui se déroule bien ne journalise rien ; seuls les
payloads illisibles produisent un avertissement, groupé par passage. Une clé absente du payload laisse la mesure correspondante
inchangée ; un payload qui n'est pas un objet JSON est ignoré.

## Les décisions automatiques

`decision_worker/` porte ce que l'application décide d'elle-même. La tâche
`decision_worker.take_the_decisions` tourne toutes les `DECISION_SECONDS` (60 s
par défaut).

Première décision, `light_the_plants` : pour chaque plante non supprimée dont
`auto_luminosity` est activé, si l'heure tombe dans la plage horaire de son type
de plante, les actionneurs de la plante qui agissent sur la lumière sont allumés ;
en dehors, ils sont éteints. Une plante dont la lumière automatique est
désactivée n'est pas touchée du tout — elle est à la main de quelqu'un d'autre.

Éteindre une lampe à la main, depuis les paramètres de l'actionneur, **fait
passer sa plante en lumière manuelle** (`auto_luminosity` à faux) : sans cela, la
décision la rallumerait dans la minute et l'interrupteur paraîtrait cassé. Le
bouton « Lumière automatique » d'une plante n'apparaît d'ailleurs que si quelque
chose peut l'éclairer.

Seconde décision, `water_the_plants` : pour chaque plante non supprimée dont
`auto_watering` est activé, l'humidité visée est **le milieu de la fourchette de
son type de plante**, `(humidity_min + humidity_max) / 2`. En dessous, les
actionneurs de la plante qui agissent sur l'humidité sont allumés ; à ce niveau
ou au-dessus, ils sont éteints. Viser le milieu plutôt que le minimum laisse de
la marge des deux côtés : une plante arrosée jusqu'à sa borne basse serait sèche
aussitôt. Une plante qui n'a jamais donné son humidité compte comme une plante
qui n'a pas soif — on ne laisse rien tourner sur une mesure qu'on n'a pas.

L'arrosage automatique se règle comme la lumière : le bouton « Arrosage
automatique » de la carte bascule `auto_watering`, et n'apparaît que si la plante
a un actionneur qui agit sur l'humidité. Basculer l'interrupteur d'une pompe à la
main, depuis les paramètres de l'actionneur — pour l'allumer comme pour
l'éteindre — **fait passer sa plante en arrosage manuel** (`auto_watering` à
faux) : toucher l'interrupteur, c'est reprendre l'eau de cette plante en main.

Les deux décisions basculent les prises par le même `decision_worker.plugs.switch`,
qui n'écrit que si l'état voulu a changé et signe sa ligne du nom de la décision
qui l'a demandé.

Une décision **écrit en base et rien d'autre** : c'est le worker MQTT qui, à son
tour, dit aux prises l'état voulu. La bascule est donc datée tout de suite
(`last_switch`) et atteint la prise au passage suivant, dans la minute. Chaque
bascule laisse une ligne dans le journal, et une décision qui ne change rien n'en
laisse aucune.

## La cohérence de l'installation

`coherence_worker/` répond à une autre question : la prise fait-elle vraiment
quelque chose ? La tâche `coherence_worker.check_the_plugs` tourne toutes les
`COHERENCE_SECONDS` (300 s par défaut) et passe en revue chaque actionneur
assigné à une plante.

Pour chacun, elle prend la mesure sur laquelle il agit (`act_on` : humidité,
lumière ou température) dans les données des capteurs de **sa** plante, et
compare la dernière valeur à celle d'il y a au moins cinq minutes :

- prise **éteinte** et la mesure **monte franchement** → avertissement ;
- prise **allumée** et la mesure **baisse ou stagne** → avertissement ;
- tout le reste → rien.

« Franchement » veut dire au moins 5 points d'humidité, 1 °C, ou un cran de
l'échelle de lumière : en dessous, la mesure ne fait que respirer. Dans l'autre
sens il n'y a pas de seuil — une prise allumée qui fait monter la mesure, même
d'un point, fait son travail.

Quatre cas ne se jugent pas, et ne disent donc rien : une prise assignée à
aucune plante, une plante dont aucun capteur ne rapporte cette mesure-là, une
dernière mesure sans rien d'assez ancien à quoi la comparer, et une dernière
mesure vieille de plus de quinze minutes — un capteur qui s'est tu n'est pas une
prise qui ne marche plus. Les mesures sont lues avec les clés de leur propre
capteur, et une lecture qui ne porte pas la mesure n'en cache pas une autre
derrière elle.

L'avertissement passe par le même cache que ceux du worker MQTT, sous le genre
`effect`, et s'affiche dans le même bandeau : « Brumisateur est allumé, mais
l'humidité ne monte pas (50 % puis 48 %) ». **Rien n'est basculé ici** : ce que
font les prises est l'affaire de l'utilisateur, le worker se contente de dire ce
qui ne colle pas.

## Tests

```
pytest
```
