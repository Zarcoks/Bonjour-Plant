"""Where the MQTT broker is, as read from the environment."""
from urllib.parse import urlparse

# The schemes we understand, with the port each one defaults to.
DEFAULT_PORTS = {'mqtt': 1883, 'mqtts': 8883, 'ws': 80, 'wss': 443}
TLS_SCHEMES = ('mqtts', 'wss')


class Broker:
    """The address and the credentials of the MQTT broker."""

    def __init__(self, host, port, username=None, password=None, use_tls=False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def __str__(self):
        return "{}:{}".format(self.host, self.port)


def broker_from_url(url):
    """
    Reads a broker out of a URL such as "mqtt://user:password@broker:1883".

    The scheme gives the default port and whether the connection is encrypted.
    """
    parsed = urlparse(url if '//' in url else '//' + url, scheme='mqtt')
    scheme = parsed.scheme.lower()
    if not parsed.hostname:
        raise ValueError("L'URL du broker MQTT n'a pas d'hôte : " + url)
    return Broker(
        host=parsed.hostname,
        port=parsed.port or DEFAULT_PORTS.get(scheme, 1883),
        username=parsed.username,
        password=parsed.password,
        use_tls=scheme in TLS_SCHEMES,
    )
