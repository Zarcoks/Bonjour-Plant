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
- `battery_worker/` : le worker qui surveille les piles des capteurs
- `static/` : fichiers statiques généraux (design system `bonjour-plant.css`,
  Bootstrap, Bootstrap Icons, HTMX, hls.js et le lecteur des caméras,
  illustration par défaut)
- `plant_management/` : app métier
  - `models.py` : `PlantType`, `GrowingPlant`, `Sensor`, `SensorData`, `Actionner`,
    `Camera`, `AppLog`
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
| `listener` | l'écoute MQTT, un processus à elle seule |
| `celery` | les tâches planifiées : synchronisation, ordres, décisions, cohérence |
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
| `/warnings/` | `warnings` | ce qui ne colle pas dans l'installation, redemandé en HTMX |
| `/warnings/<sujet>/<id>/<genre>/dismiss/` | `dismiss_warning` | POST : « c'est réglé », cet écart-là est retiré |
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
| `/actionners/<id>/` | `actionner_detail` | GET : carte dépliée et modifiable, POST : enregistrement |
| `/actionners/<id>/card/` | `actionner_card` | carte repliée (sert aussi de « Annuler ») |
| `/actionners/<id>/switch/` | `switch_actionner` | POST : bascule la prise, et l'ordre part aussitôt |
| `/actionners/<id>/delete/` | `delete_actionner` | POST : suppression, après confirmation |
| `/video/` | `video` | les caméras de l'installation, et celle qu'on regarde |
| `/video/create/` | `create_camera` | GET : formulaire d'ajout, POST : ajout |
| `/video/<id>/delete/` | `delete_camera` | POST : suppression, après confirmation |
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

## La carte dépliée d'une plante

Cliquer sur une plante déplie sa carte. On y trouve, dans cet ordre :

1. **le flux de sa caméra**, en grand, quand une caméra lui est assignée — joué
   par le même lecteur que la page vidéo, démarré au swap HTMX et détruit dès
   que la carte se referme ;
2. **ses dernières mesures** en grand : humidité, lumière, température, aux
   couleurs des courbes de la page métriques ;
3. **ses champs modifiables**, photo, signes et boutons compris, comme avant.

Une plante récoltée n'affiche pas de mesures, comme sur sa carte repliée. La
carte repliée, elle, ne joue rien : un lecteur par plante sur une page qui en
liste dix tirerait dix flux du Raspberry Pi pour rien.

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
publient. Chaque capteur porte donc quatre champs texte, modifiables dans son
interface : `humidity_payload_label`, `luminosity_payload_label`,
`temperature_payload_label` et `battery_payload_label`. Ils valent `humidity`,
`luminosity`, `temperature` et `battery` par défaut ; un champ laissé vide
reprend cette valeur à l'enregistrement, et les méthodes `get_*_label()` du
modèle assurent le même repli pour une ligne écrite hors de l'interface.

### La batterie sur la carte

Les capteurs disent aussi, dans le même payload, ce qu'il leur reste de
batterie. Cette charge est écrite sur le capteur lui-même (`battery_level`, en
pourcentage) par le worker MQTT, **à l'arrivée du message et avant tout le
reste** : un capteur assigné à aucune plante ne garde aucune mesure, et ses
piles s'usent tout autant. Un payload qui ne dit rien de la charge laisse la
dernière connue en place — le silence n'est pas une pile vide — et une charge
hors de l'échelle des pourcentages n'est pas une charge.

La carte repliée en fait une ligne, sous le modèle : « Batterie 84 % », le
pourcentage tel que le capteur l'a rapporté. **Rien n'est traduit** — ni palier,
ni niveau, ni icône qui se remplit : la charge est un pourcentage, elle est
affichée comme tel. La ligne passe simplement en terre cuite en dessous de
`LOW_BATTERY` (10 %), le seul jugement porté sur la charge (`battery_is_low()`),
et le bandeau de la page principale dit le reste. Un capteur qui n'a jamais parlé
de ses piles affiche « Batterie inconnue » plutôt que rien : ne rien afficher
laisserait croire à une carte sans information.

## Les actionneurs

Un actionneur est une prise connectée avec un appareil dessus — lampe UV,
humidificateur, tapis chauffant. Sa page reprend le CRUD des capteurs : grille de
cartes, carte dépliée modifiable, photo par défaut, création en HTMX,
suppression après confirmation.

Il porte son nom, sa photo, son état (`is_on`), la plante à laquelle il est
assigné ou non, et le facteur sur lequel il agit (`act_on` : humidité, lumière ou
température, les mêmes noms que les mesures).

Son état ne fait **pas** partie du formulaire : il se bascule depuis un bouton de
la carte, comme la lumière et l'arrosage automatiques d'une plante. Le bouton
« Alimentation » poste sur `switch_actionner`, qui inverse `is_on`, date
`last_switch` et renvoie la carte ; modifier l'actionneur ne touche donc jamais à
son état, et une prise créée l'est toujours éteinte. Le clic est *consommé*
(`hx-trigger="click consume"`) pour ne pas déplier la carte au passage.

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

Le passage suivant n'est cependant pas attendu quand c'est l'utilisateur qui
demande quelque chose : le bouton d'un actionneur appelle `switch_the_plugs` dans
la requête même, juste après avoir écrit l'état voulu. La prise suit donc au clic
plutôt qu'à la minute. La tâche avale les erreurs du broker : une publication qui
échoue laisse une ligne dans le journal et la page répond quand même.

Le journal garde les deux versants d'une bascule : ce que l'utilisateur a
demandé (« L'utilisateur veut allumer l'actionneur … », écrit par le bouton)
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
qu'elle n'a pas (plus bas). Un capteur, lui, a un seul genre : `battery`, les
piles qui s'épuisent. Le cache porte donc **une entrée par appareil et par
genre**, chacune signalée et réglée séparément ; c'est le sujet (`actionner` ou
`sensor`) et le genre qui voyagent dans l'URL de « C'est réglé ». Chaque
avertissement porte la phrase à afficher, qui suit le nom de l'appareil sur la
page comme dans le journal.

`warn(appareil, genre, phrase)` se moque de ce qu'on lui passe : le sujet est lu
sur le modèle de l'appareil lui-même, donc signaler quelque chose s'écrit pareil
pour une prise et pour un capteur.

Le bandeau vit en haut de la page « Mes plantes », dont il porte maintenant la
route (`warnings`) : c'est la page qui le montre. Il se redemande tout seul
toutes les 15 secondes, en HTMX, donc un appareil qui dérive pendant que la page
est ouverte apparaît sans rechargement ; « C'est réglé » retire une ligne et
renvoie le bandeau, les autres écarts restent. Les écarts sont lus depuis le
cache en partant des appareils de la base croisés avec leurs genres — jamais en
listant le cache lui-même.

## La page vidéo

La page `/video/` montre les caméras de l'installation en direct : la liste à
gauche, celle qu'on regarde à droite. Une caméra se déclare avec deux choses, un
nom et l'adresse de son flux :

```
Caméra du balcon    http://192.168.1.42:8888/balcon/index.m3u8
```

L'adresse attendue est **celle du flux HLS republié par le Raspberry Pi**, pas
celle de la caméra. C'est MediaMTX, sur le Pi, qui va chercher la caméra en RTSP
sur le réseau local et rediffuse son flux en HLS ; l'application ne connaît que
cette rediffusion, et la caméra n'est jamais jointe directement.

C'est du HLS qui est joué, et non du RTSP, parce qu'aucun navigateur ne lit le
RTSP : le HLS n'est qu'une playlist servie en HTTP, qu'une balise `<video>`
consomme. Et plutôt que du WebRTC, parce que sur un réseau overlay comme NetBird
la négociation ICE demande à MediaMTX de connaître ses propres adresses sur
l'overlay, là où le HLS n'est que du HTTP. Quelques secondes de latence en plus,
et une page qui marche partout où le Pi est joignable.

### Une caméra peut suivre une plante

Comme un capteur ou une prise, une caméra s'assigne à une plante — ou à aucune.
La caméra assignée est celle dont le flux s'affiche sur la carte de la plante,
page « Mes plantes » ; si plusieurs caméras suivent la même plante, la première
par ordre alphabétique est celle qui est jouée. Supprimer une plante libère ses
caméras comme elle libère ses capteurs et ses prises.

### Ce qui est vérifié de l'adresse

Deux choses seulement, celles sans lesquelles un navigateur ne peut rien : un
schéma qu'il sait suivre (`http://` ou `https://` — une adresse `rtsp://` est ce
que MediaMTX lit, pas ce qu'il sert) et une machine où aller. Le reste est
enregistré tel quel, `index.m3u8` compris ou non : c'est l'adresse à laquelle on
regarde le flux, et celui qui la saisit est celui qui sait à quoi elle
ressemble.

### Le lecteur

La lecture est faite par `hls.js` (`static/camera-player.js`), sauf sur Safari
qui lit le HLS tout seul et mieux. Un lecteur est démarré après chaque swap
HTMX, et détruit dès que sa balise `<video>` a quitté la page : un lecteur que
personne ne regarde continuerait sinon à tirer le flux du Raspberry Pi. Un flux
en direct méritant qu'on insiste, une erreur fatale est retentée trois fois
(`startLoad` pour le réseau, `recoverMediaError` pour le média) avant que le
cadre n'affiche que le flux n'arrive pas ; le compteur repart à zéro dès qu'un
fragment est de nouveau lu. Le bouton « Relancer » redemande le flux.

### Ce que la page fait sans se recharger

Comme partout ailleurs, tout passe par HTMX. Choisir une caméra, en ajouter une
ou en supprimer une remplace le même bloc — la liste et l'image ensemble — ce qui
règle d'un coup le cas de la caméra supprimée pendant qu'on la regardait.
L'ajout répond avec la nouvelle caméra en train de jouer, plus un swap *out of
band* qui referme le formulaire.

## Le worker MQTT

Le paquet `mqtt_worker/` écoute l'installation. L'adresse du broker vient de
`MQTT_BROKER_URL` dans le `.env` (`mqtt://`, `mqtts://`, avec identifiants
éventuels), les topics viennent du champ `mqtt_topic` des capteurs et du
`mqtt_topic_in` des actionneurs qui rapportent leur état.

L'écoute tourne dans **son propre conteneur** (`listener`), lancé par
`manage.py listen_sensors`, et non dans une tâche Celery : une boucle infinie
n'est pas une tâche, et Docker sait déjà surveiller un processus. Un plantage est
donc rattrapé par `restart: unless-stopped`, sans surveillance à écrire.

Toutes les `MQTT_SYNC_SECONDS` (30 s par défaut), l'écoute relit la table des
capteurs et met ses abonnements à jour : un capteur ajouté est écouté, un
capteur supprimé ou dont le topic change voit son ancien topic abandonné. Une
reconnexion au broker reprend tous les abonnements, puisqu'une nouvelle session
MQTT n'en porte aucun.

À l'arrivée d'un message, une ligne `sensor_data` est écrite par capteur assigné
qui écoute ce topic, et le même message est relu pour les actionneurs qui
rapportent sur ce topic. **Une donnée venant d'un capteur assigné à aucune plante
est abandonnée**, comme celle d'un topic que plus aucun capteur ne réclame. Les
topics à jokers (`bonjour-plant/+/humidity`) sont gérés.

Une seule chose échappe à cette règle : la **charge de la batterie** que le
capteur rapporte de lui-même, écrite sur le capteur avant même le test de
l'assignation (voir « La batterie sur la carte »). Les piles d'un capteur sont
son affaire, pas celle d'une plante.

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

### L'ordre de démarrage

`listener` et `celery` attendent que `django-web` réponde, car c'est ce qui
signale que son `entrypoint.sh` a fini d'appliquer les migrations : ces deux
services interrogent un schéma qu'ils ne migrent pas eux-mêmes. Sans cette
attente, l'écoute part sur une colonne qui n'existe pas encore.

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

Éteindre une lampe à la main, depuis le bouton de sa carte, **fait passer sa
plante en lumière manuelle** (`auto_luminosity` à faux) : sans cela, la décision
la rallumerait dans la minute et l'interrupteur paraîtrait cassé. Le
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
main, depuis le bouton de sa carte — pour l'allumer comme pour l'éteindre —
**fait passer sa plante en arrosage manuel** (`auto_watering` à faux) : toucher
l'interrupteur, c'est reprendre l'eau de cette plante en main.

Les deux décisions basculent les prises par le même `decision_worker.plugs.switch`,
qui n'écrit que si l'état voulu a changé et signe sa ligne du nom de la décision
qui l'a demandé.

Une décision **écrit en base et rien d'autre** : c'est le worker MQTT qui, à son
tour, dit aux prises l'état voulu. La bascule est donc datée tout de suite
(`last_switch`) et atteint la prise au passage suivant, dans la minute. Chaque
bascule laisse une ligne dans le journal, et une décision qui ne change rien n'en
laisse aucune.

### Une automatisation activée est appliquée tout de suite

Les deux décisions tournent aussi **à la demande**, en dehors de leur horaire :
activer la lumière automatique d'une plante lance `light_the_plants` dans la
requête, activer son arrosage automatique lance `water_the_plants`, et si la
décision a basculé quelque chose, `switch_the_plugs` part derrière. La lampe
s'allume donc au clic, et non au prochain passage du worker — un bouton qui ne
fait rien pendant une minute passe pour un bouton cassé.

C'est `take_the_decision_now` (dans les vues des plantes) qui enchaîne les deux,
et seulement dans le sens de l'activation : désactiver une automatisation ne
décide rien, puisque la décision cesse justement de regarder cette plante.
L'horaire reste en place pour la suite : le lancement à la demande ne remplace
rien, il évite l'attente.

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

## Les piles des capteurs

`battery_worker/` pose une question à part : les capteurs ont-ils encore de quoi
parler ? Ce n'est pas une affaire de cohérence — rien n'est comparé à rien, et
aucun capteur n'est démenti — d'où un worker à lui seul. La tâche
`battery_worker.check_the_batteries` tourne toutes les `BATTERY_SECONDS`
(3600 s par défaut) et passe en revue la charge que chaque capteur non supprimé a
rapportée de lui-même. En dessous de `LOW_BATTERY` (10 %), un avertissement est
déposé sous le genre `battery` :

```
Le capteur Luxmètre du salon n'a plus que 6 % de batterie : il est temps de
changer ses piles
```

Une heure suffit : une pile s'use en semaines, et le capteur ne se taira pas
entre deux passages. Un capteur qui n'a jamais rien dit de ses piles n'est pas
même regardé — le silence n'est pas une pile vide — et un capteur assigné à
aucune plante l'est comme les autres : ses piles sont son affaire, pas celle
d'une plante. **Rien n'est écrit sur les capteurs ici** non plus : changer les
piles est l'affaire de l'utilisateur, et l'avertissement tient jusqu'à ce qu'il
appuie sur « C'est réglé ». Une pile changée ne retire donc pas le message
d'elle-même, comme une prise rentrée dans le rang ne retire pas le sien.

Le worker MQTT est le seul à écrire quelque chose sur les capteurs (la charge, à
l'arrivée du message) ; celui-ci ne fait que la lire.

## Tests

```
pytest
```
