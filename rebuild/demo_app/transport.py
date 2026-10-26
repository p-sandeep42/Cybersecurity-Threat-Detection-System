"""Keep local demo traffic local, even when the shell configures an HTTP proxy."""

from ipaddress import ip_address
from urllib.parse import urlsplit

import requests


def is_loopback_url(url: str) -> bool:
    hostname = urlsplit(url).hostname
    if hostname == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


def post_json(url: str, **kwargs):
    """Ignore proxy/netrc environment settings only for explicit loopback targets.

    Remote integrations retain Requests' usual proxy and certificate settings.
    Redirects are disabled by callers so a local request cannot forward its key.
    """
    if not is_loopback_url(url):
        return requests.post(url, **kwargs)
    with requests.Session() as session:
        session.trust_env = False
        return session.post(url, **kwargs)
