"""Module for global dogpile cache regions"""
from flask_dogpile_cache import make_region


def key_mangler(key):
    """Maintain unique redis keys for dogpile needs

    Mangle the key with a prefix to prevent accidental cache collisions
    """
    return 'dogpile_cache:' + key


# Region for caching with hourly updates
hourly_cache = make_region(
    key_mangler=key_mangler).configure(
          'dogpile.cache.redis',
          expiration_time=3600,
          arguments={'url': "127.0.0.1:11211"}
      )
