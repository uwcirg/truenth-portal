"""Module for global dogpile cache regions"""
from flask_dogpile_cache import DogpileCache

# Global cache instance.  Regions defined in configuration.
dogpile_cache = DogpileCache()
