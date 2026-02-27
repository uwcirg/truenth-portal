from importlib.metadata import PackageNotFoundError, version as _get_version

try:
    __version__ = _get_version("portal")
except PackageNotFoundError:
    __version__ = "0.0.0"
