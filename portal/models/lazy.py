from sqlalchemy.orm.util import class_mapper

from ..extensions import db

def _is_sql_wrapper(instance):
    """Determines if instance is a SQLAlchemy wrapper (ORM instance)"""
    try:
        class_mapper(instance.__class__)
        return True
    except:
        return False


def lazyprop(fn):
    """Property decorator for lazy intialization (load on first request)"""
    attr_name = '_lazy_' + fn.__name__
    @property
    def _lazyprop(self):
        if not hasattr(self, attr_name):
            #print "loading {}".format(attr_name)
            setattr(self, attr_name, fn(self))
        # at least for testing, we run into session errors
        # make sure it's accessible before returning or merge
        # but only if it's an ORM instance
        attr = getattr(self, attr_name)
        if _is_sql_wrapper(attr):
            try:
                test = attr.id
            except:
                attr = db.session.merge(attr)
        return attr
    return _lazyprop
