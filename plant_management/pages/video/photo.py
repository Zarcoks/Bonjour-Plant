"""
Taking one photograph off a camera.

A Tapo C210 has no way of handing over a still picture: `pytapo`, the library
that reverse engineers these cameras, drives them — presets, privacy mode,
detection, recordings on the card — but has no snapshot of any kind. What the
camera does publish is its RTSP feed, on a path and under an account that are
known for this model, so a photograph is one frame pulled off that feed.

Knowing the path and the account is exactly what makes a model supported: a
camera we have never met is left alone rather than guessed at.

The address carries the password of the camera. It is built here, handed to
ffmpeg, and never written anywhere else: not in the page, not in the journal.
"""
import subprocess
from urllib.parse import quote

from core.app import app
from plant_management.models import RTSP_PORT, RTSP_STREAM_PATH

logger = app.module_logger("video")

# How long the camera is given to hand over one frame, in seconds.
PHOTO_TIMEOUT = 15

# How good the picture is, on the ffmpeg scale where 2 is the best and 31 the
# worst. A plant does not need more.
JPEG_QUALITY = 4


def rtsp_url(camera):
    """
    Where to pull that camera, credentials included.

    **Carries the password**: for ffmpeg, and for nothing else. The parts are
    quoted, so that a password with an `@` or a `/` in it does not break the
    address in two.
    """
    credentials = ''
    if camera.username:
        credentials = "{}:{}@".format(quote(camera.username, safe=''),
                                      quote(camera.password, safe=''))
    return "rtsp://{}{}:{}/{}".format(credentials, camera.local_ip, RTSP_PORT, RTSP_STREAM_PATH)


def ffmpeg_command(url):
    """One frame, off the feed, as a JPEG on the standard output."""
    return [
        'ffmpeg',
        '-rtsp_transport', 'tcp',
        '-i', url,
        '-frames:v', '1',
        '-q:v', str(JPEG_QUALITY),
        '-f', 'image2',
        '-',
    ]


def take(camera, timeout=PHOTO_TIMEOUT):
    """
    One photograph of that camera, or None when it could not be taken.

    Answers None rather than raising: a camera that is off, that refused the
    credentials or that is simply not there is an ordinary state of the
    installation, and the page says so in its own words.
    """
    if not camera.is_supported():
        return None
    try:
        taken = subprocess.run(ffmpeg_command(rtsp_url(camera)),
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning("La caméra " + camera.name + " n'a pas rendu de photo à temps")
        return None
    except FileNotFoundError:
        logger.error("La commande ffmpeg est introuvable : aucune photo ne peut être prise")
        return None
    if taken.returncode != 0 or not taken.stdout:
        logger.warning("La photo de la caméra " + camera.name + " n'a pas pu être prise")
        return None
    return taken.stdout
