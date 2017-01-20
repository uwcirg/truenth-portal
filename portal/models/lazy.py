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
    """Property decorator for lazy intialization (load on first request)

    Useful on any expensive to load attribute on any class.  Simply
    decorate the 'getter' with @lazyprop, where the function definition
    loads the object to be assigned to the given attribute.

    """
    attr_name = '_lazy_{}'.format(fn.__name__)
    disable_cache = True
    @property
    def _lazyprop(self):
        if disable_cache:
            return fn(self)

        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))

        attr = getattr(self, attr_name)

        # ORM objects (especially in testing) are occasionally detached
        if _is_sql_wrapper(attr):
            if attr not in db.session:
                attr = db.session.merge(attr)
                setattr(self, attr_name, attr)
        return attr
    return _lazyprop


def query_by_name(cls, name):
    """returns a lazy load function capable of caching object

    Use this alternative for classes with dynamic attributes (names
    not hardcoded in class definition), as property decorators
    (i.e. @lazyprop) don't function properly.

    NB - attribute instances must be unique over (cls.__name__, name)
    within the containing class to avoid collisions.

    @param cls: ORM class to query
    @param name: name field in ORM class to uniquely define object

    """
    attr_name = '_lazy_{}_{}'.format(cls.__name__, name)
    def lookup(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, cls.query.filter_by(name=name).one())
        attr = getattr(self, attr_name)

        # ORM objects (especially in testing) are occasionally detached
        if attr not in db.session:
            attr = db.session.merge(attr)
            setattr(self, attr_name, attr)
        return attr
    return lookup
