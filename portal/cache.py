from flask import request, url_for
from flask_caching import Cache

# Configured during app configuration
cache = Cache()

# Human readable constants, values in seconds, for cache timeouts
TWO_HOURS = 2*60*60
FIVE_MINS = 5*60


def request_args_in_key():
    """Set as `key_prefix=request_args_in_key` for safe view caching

    By default, cache.cached() uses only the request path as the key.
    For any views returning different results with query string parameters,
    need to include those parameters in the cache key

    :return: key for caching

    """
    return url_for(request.endpoint, **request.args)
