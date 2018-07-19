from __future__ import unicode_literals  # isort:skip

from flask import abort


def check_int(i):
    try:
        return int(i)
    except ValueError:
        abort(400, "invalid input '{}' - must be an integer".format(i))
