# Bonjour Plant

Une application Django qui assiste l'entretien des plantes, pour le rendre
simple comme bonjour.

## Structure

- `core/` : configuration du projet (settings, urls, wsgi/asgi)
- `static/` : fichiers statiques généraux de l'application
- `plant_management/` : app métier (vues, urls, modèles, templates)
- `tests/` : tests d'intégration pytest

## Lancer en local

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

La page d'accueil est ensuite disponible sur http://127.0.0.1:8000/

Les réglages se surchargent par variables d'environnement, voir `.env.example`.

## Tests

```
pytest
```
