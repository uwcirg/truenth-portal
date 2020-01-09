from flask_caching import Cache


# Simple init, replaced during app configuration
cache = Cache(config={'CACHE_TYPE': 'simple'})


# Human readable constants, values in seconds, for cache timeouts
TWO_HOURS = 2*60*60
