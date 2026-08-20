"""Raises what a development run needs beside `runserver`."""
import os
import signal
import socket
import subprocess
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# The services the Celery worker needs. Each one is started in a container when
# nothing already answers on its port.
SERVICES = [
    {
        'name': "Redis",
        'port': 6379,
        'container': "bonjour-plant-dev-redis",
        'image': "redis:7-alpine",
        'options': [],
        'command': [],
    },
    {
        'name': "Mosquitto",
        'port': 1883,
        'container': "bonjour-plant-dev-mqtt",
        'image': "eclipse-mosquitto:2",
        'options': ['-v', str(settings.BASE_DIR / 'mosquitto.conf') + ":/mosquitto/config/mosquitto.conf:ro"],
        'command': ["mosquitto", "-c", "/mosquitto/config/mosquitto.conf"],
    },
]

HOST = "localhost"

# How long we give a container to answer on its port.
STARTUP_TIMEOUT_SECONDS = 30

# How long we give the worker to leave, first on its own terms, then for good.
WARM_SHUTDOWN_SECONDS = 3
COLD_SHUTDOWN_SECONDS = 8


def is_reachable(port, timeout=0.5):
    """Whether something already answers on that port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(timeout)
        return probe.connect_ex((HOST, port)) == 0


class Command(BaseCommand):
    help = ("Starts the services a development run needs — Redis, an MQTT broker — then runs the "
            "Celery worker in the foreground. Run `runserver` beside it.")

    def say(self, message, style=None):
        """Writes a line, and flushes it: the Celery worker shares this output."""
        self.stdout.write(style(message) if style else message)
        self.stdout.flush()

    def claim_signals(self):
        """
        Leaves cleanly however the order comes.

        A shell that starts a job in the background hands it a SIGINT set to
        ignored, and Python then keeps it that way: the handler is installed
        here so that the services are always stopped on the way out.
        """
        def leave(number, frame):
            raise KeyboardInterrupt

        for number in (signal.SIGINT, signal.SIGTERM):
            signal.signal(number, leave)

    def handle(self, *args, **options):
        self.claim_signals()
        self.check_docker()
        started = []
        try:
            for service in SERVICES:
                if self.start(service):
                    started.append(service)
            self.run_celery()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop(started)

    # ── Docker ────────────────────────────────────────────────

    def check_docker(self):
        """Docker is only needed for the services that are not up yet."""
        if all(is_reachable(service['port']) for service in SERVICES):
            return
        try:
            subprocess.run(["docker", "version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            raise CommandError(
                "Docker n'est pas disponible, et les services ne tournent pas encore.\n"
                "Démarrez Docker, ou lancez vous-même un Redis sur le port 6379 et un broker MQTT "
                "sur le port 1883."
            )

    def start(self, service):
        """Starts one service, unless something already answers on its port. Says if it started it."""
        if is_reachable(service['port']):
            self.say("{} répond déjà sur le port {} : réutilisé.".format(service['name'], service['port']))
            return False

        self.say("Démarrage de {}...".format(service['name']))
        subprocess.run(
            ["docker", "run", "--detach", "--rm",
             "--name", service['container'],
             "--publish", "{}:{}".format(service['port'], service['port'])]
            + service['options'] + [service['image']] + service['command'],
            capture_output=True, check=True,
        )
        self.wait_for(service)
        return True

    def wait_for(self, service):
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if is_reachable(service['port']):
                self.say("{} écoute sur le port {}.".format(service['name'], service['port']),
                         style=self.style.SUCCESS)
                return
            time.sleep(0.5)
        raise CommandError("{} n'a pas répondu sur le port {}.".format(service['name'], service['port']))

    def stop(self, started):
        for service in started:
            self.say("Arrêt de {}...".format(service['name']))
            subprocess.run(["docker", "stop", service['container']], capture_output=True)

    # ── Celery ────────────────────────────────────────────────

    def stop_worker(self, worker):
        """
        Asks the worker to leave, then insists.

        Signals reach the whole group: Celery runs a pool of children, and
        signalling the parent alone would leave them behind. The first
        interruption asks for a warm shutdown, which waits for the running
        tasks — and the listening task never ends on its own, hence the second
        one, which Celery reads as a cold shutdown.
        """
        group = os.getpgid(worker.pid)
        for delay in (WARM_SHUTDOWN_SECONDS, COLD_SHUTDOWN_SECONDS):
            os.killpg(group, signal.SIGINT)
            try:
                worker.wait(timeout=delay)
                return
            except subprocess.TimeoutExpired:
                continue
        self.say("Le worker ne s'arrête pas : il est terminé de force.")
        os.killpg(group, signal.SIGKILL)
        worker.wait()

    def run_celery(self):
        """
        Runs the worker in the foreground, until interrupted.

        The worker starts the MQTT listening on its own, so a development run
        listens to the sensors like the deployed one.
        """
        self.say("\nLe worker Celery démarre. Lancez `python manage.py runserver` à côté, "
                 "et Ctrl-C ici pour tout arrêter.\n", style=self.style.MIGRATE_HEADING)
        worker = subprocess.Popen(
            [sys.executable, "-m", "celery", "-A", "core", "worker", "-l", "INFO", "--concurrency", "2"],
            env=dict(os.environ,
                     REDIS_URL="redis://{}:6379/0".format(HOST),
                     MQTT_BROKER_URL="mqtt://{}:1883".format(HOST)),
            # Its own group, so that the whole pool can be signalled at once.
            start_new_session=True,
        )
        try:
            worker.wait()
        except KeyboardInterrupt:
            self.stop_worker(worker)
            raise
