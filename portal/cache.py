from flask_caching import Cache


# Simple init, replaced during app configuration
cache = Cache(config={'CACHE_TYPE': 'simple'})
