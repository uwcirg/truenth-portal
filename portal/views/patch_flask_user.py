"""workarounds to flask_user problems"""
from urlparse import urlsplit, urlunsplit


def patch_make_safe_url(url):
    """Patch flask_user.make_safe_url() to include '?'

    Turns an usafe absolute URL into a safe relative URL by removing
    the scheme and the hostname
    Example:
        make_safe_url('http://hostname/path1/path2?q1=v1&q2=v2#fragment')
        returns: '/path1/path2?q1=v1&q2=v2#fragment

    """
    parts = urlsplit(url)
    safe_url = urlunsplit(
        (None, None, parts.path, parts.query, parts.fragment))
    return safe_url
