"""Cross Domain Decorators"""
from datetime import timedelta
from functools import update_wrapper

from flask import current_app, make_response, request
from past.builtins import basestring

from ..models.client import validate_origin


def crossdomain(
        origin=None,
        methods=None,
        headers=(
            'Authorization',
            'X-Requested-With',
            'X-CSRFToken',
            'Content-Type'
        ),
        max_age=21600, automatic_options=True):
    """Decorator to add specified crossdomain headers to response

    :param origin: '*' to allow all origins, otherwise a string with
        a single origin or a list of origins that might
        access the resource.  If no origin is provided, use
        request.headers['Origin'], but ONLY if it validates.  If
        no origin is provided and the request doesn't include an
        **Origin** header, no CORS headers will be added.
    :param methods: Optionally a list of methods that are allowed
        for this view. If not provided it will allow
        all methods that are implemented.
    :param headers: Optionally a list of headers that are allowed
        for this request.
    :param max_age: The number of seconds as integer or timedelta
        object for which the preflighted request is valid.
    :param automatic_options: If enabled the decorator will use the
        default Flask OPTIONS response and attach the headers there,
        otherwise the view function will be called to generate an
        appropriate response.

    :raises :py:exc:`werkzeug.exceptions.Unauthorized`: if no origin is provided and the one in
        request.headers['Origin'] doesn't validate as one we know.

    """

    def get_headers():
        if headers is not None and not isinstance(headers, basestring):
            return ', '.join(x.upper() for x in headers)
        return headers

    def get_methods():
        if methods is not None:
            return ', '.join(sorted(x.upper() for x in methods))

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def get_origin():
        """Given origin used blind, request.origin requires validation"""
        if origin:
            if not isinstance(origin, basestring):
                return ', '.join(origin)
            return origin

        use_origin = None
        if 'Origin' in request.headers:
            use_origin = request.headers['Origin']
        if use_origin:
            validate_origin(use_origin)
        return use_origin

    def get_max_age():
        if isinstance(max_age, timedelta):
            return str(max_age.total_seconds())
        return str(max_age)

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))

            origin = get_origin()
            if origin:
                h = resp.headers
                h['Access-Control-Allow-Credentials'] = 'true'
                h['Access-Control-Allow-Origin'] = origin
                h['Access-Control-Allow-Methods'] = get_methods()
                h['Access-Control-Max-Age'] = get_max_age()
                h['Access-Control-Allow-Headers'] = get_headers()
                h['Access-Control-Expose-Headers'] = 'content-length'
            return resp

        f.provide_automatic_options = False
        f.required_methods = getattr(f, 'required_methods', set())
        f.required_methods.add('OPTIONS')

        return update_wrapper(wrapped_function, f)

    return decorator
