from sqlalchemy.orm.util import class_mapper
from sqlalchemy.orm.exc import DetachedInstanceError

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
            setattr(self, attr_name, fn(self))

        attr = getattr(self, attr_name)

        # ORM objects (especially in testing) are occasionally detached
        if _is_sql_wrapper(attr):
            try:
                test = attr.id
                assert test
            except DetachedInstanceError:
                attr = db.session.merge(attr)
                if attr.id:
                    setattr(self, attr_name, attr)
                else:
                    setattr(self, attr_name, fn(self))
        return attr
    return _lazyprop
