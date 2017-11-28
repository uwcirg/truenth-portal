"""Persistence details for Model Classes"""
from flask import current_app
import json
import os
from StringIO import StringIO
from sqlalchemy import exc

from ..database import db
from ..dict_tools import dict_match
from ..date_tools import FHIR_datetime
from ..models.identifier import Identifier
from ..trace import trace

class ModelPersistence(object):
    """Adapter class to handle persistence of model tables"""
    VERSION = '0.2'

    def __init__(
            self, model_class, lookup_field='id', sequence_name=None):
        """Initialize adapter for given model class"""
        self.model = model_class
        self.lookup_field = lookup_field
        self.sequence_name = sequence_name

    @staticmethod
    def _log(msg):
        current_app.logger.info(msg)
        trace(msg)

    def __header__(self, data):
        data['resourceType'] = 'Bundle'
        data['id'] = 'SitePersistence v{}'.format(self.VERSION)
        data['meta'] = {'fhir_comments': [
            "export of dynamic site data from host",
            "{}".format(current_app.config.get('SERVER_NAME'))],
            'lastUpdated': FHIR_datetime.now()}
        data['type'] = 'document'
        return data

    def __read__(self, target_dir):
        scope = self.model.__name__ if self.model else None
        self.filename = persistence_filename(
            scope=scope, target_dir=target_dir)
        with open(self.filename, 'r') as f:
            data = json.load(f)
        self.__verify_header__(data)
        return data

    def __write__(self, data, target_dir):
        scope = self.model.__name__ if self.model else None
        self.filename = persistence_filename(
            scope=scope, target_dir=target_dir)
        if data:
            with open(self.filename, 'w') as f:
                f.write(json.dumps(data, indent=2, sort_keys=True, separators=(',', ': ')))
            self._log("Wrote site persistence to `{}`".format(self.filename))

    def __verify_header__(self, data):
        """Make sure header conforms to what we're looking for"""
        if data.get('resourceType') != 'Bundle':
            raise ValueError("expected 'Bundle' resourceType not found")
        if data.get('id') != 'SitePersistence v{}'.format(self.VERSION):
            raise ValueError("unexpected SitePersistence version {}".format(
                data.get('id')))

    def export(self, target_dir):
        d = self.__header__({})
        d['entry'] = self.serialize()
        self.__write__(data=d, target_dir=target_dir)

    def import_(self, keep_unmentioned, target_dir):
        objs_seen = []
        data = self.__read__(target_dir=target_dir)
        for o in data['entry']:
            if not o.get('resourceType') == self.model.__name__:
                raise ValueError(
                    "Import {} error, Found unexpected '{}' resource".format(
                        self.model.__name__, o.get('resourceType')))
            result = self.update(o)
            db.session.commit()
            objs_seen.append(result.id)

        # Delete any not named
        if not keep_unmentioned:
            query = self.model.query.filter(
                ~getattr(self.model, 'id').in_(
                    objs_seen)) if objs_seen else []
            for obj in query:
                current_app.logger.info(
                    "Deleting {} not mentioned in "
                    "persistence file".format(obj))
            if query:
                query.delete(synchronize_session=False)

        self.update_sequence()
        trace("Import of {} complete".format(self.model.__name__))

    def serialize(self):
        if hasattr(self.model, 'as_fhir'):
            serialize = 'as_fhir'
        else:
            serialize = 'as_json'

        results = []

        if isinstance(self.lookup_field, tuple):
            order_col = tuple(
                self.model.__table__.c[field].asc() for field in
                self.lookup_field)
            for item in self.model.query.order_by(*order_col).all():
                results.append(getattr(item, serialize)())
        else:
            order_col = (
                self.model.__table__.c[self.lookup_field].asc()
                if self.lookup_field != "identifier" else "id")
            for item in self.model.query.order_by(order_col).all():
                results.append(getattr(item, serialize)())

        return results

    def lookup_existing(self, new_obj, new_data):
        match, field_description = None, None
        if self.lookup_field == 'id':
            field_description = unicode(new_obj.id)
            match = (
                self.model.query.get(new_obj.id)
                if new_obj.id is not None else None)
        elif self.lookup_field == 'identifier':
            ids = new_data.get('identifier')
            if len(ids) == 1:
                id = Identifier.from_fhir(ids[0]).add_if_not_found()
                field_description = unicode(id)
                match = self.model.find_by_identifier(id) if id else None
            elif len(ids) > 1:
                raise ValueError(
                    "Multiple identifiers for {} "
                    "don't know which to match on".format(new_data))
        elif isinstance(self.lookup_field, tuple):
            # Composite key case
            args = {k: new_data.get(k) for k in self.lookup_field}
            field_description = unicode(args)
            match = self.model.query.filter_by(**args).first()
        else:
            args = {self.lookup_field: new_data[self.lookup_field]}
            field_description = getattr(new_obj, self.lookup_field)
            match = self.model.query.filter_by(**args).first()
        return match, field_description

    def update(self, new_data):

        if hasattr(self.model, 'from_fhir'):
            from_method = self.model.from_fhir
            update = 'update_from_fhir'
            serialize = 'as_fhir'
        else:
            from_method = self.model.from_json
            update = 'update_from_json'
            serialize = 'as_json'

        merged = None
        new_obj = from_method(new_data)
        existing, id_description = self.lookup_existing(
            new_obj=new_obj, new_data=new_data)

        if existing:
            details = StringIO()
            if not dict_match(new_data, getattr(existing, serialize)(), details):
                self._log(
                    "{type} {id} collision on import.  {details}".format(
                        type=self.model.__name__,
                        id=id_description,
                        details=details.getvalue()))
                merged = getattr(existing, update)(new_data)
        else:
            self._log("{type} {id} not found - importing".format(
                type=self.model.__name__,
                id=id_description))
            db.session.add(new_obj)
        return merged or new_obj

    def update_sequence(self):
        """ Bump sequence numbers if necessary

        As the import/update methods don't use the sequences, best
        to manually set it to a value greater than the current max,
        to avoid unique constraint violations in the future.

        """
        try:
            max_known = db.engine.execute(
                "SELECT MAX(id) FROM {table}".format(
                    table=self.model.__tablename__)).fetchone()[0]
            currval = db.engine.execute(
                "SELECT CURRVAL('{}')".format(self.sequence_name))
        except exc.OperationalError as oe:
            if 'not yet defined' in str(oe):
                currval = db.engine.execute(
                    "SELECT NEXTVAL('{}')".format(self.sequence_name))
        if currval.fetchone()[0] < max_known:
            db.engine.execute(
                "SELECT SETVAL('{}', {})".format(
                    self.sequence_name, max_known + 1))


def export_model(cls, lookup_field, target_dir):
    model_persistence = ModelPersistence(cls, lookup_field=lookup_field)
    return model_persistence.export(target_dir=target_dir)


def import_model(
        cls, sequence_name, lookup_field, keep_unmentioned=True,
        target_dir=None):
    model_persistence = ModelPersistence(
        cls, lookup_field=lookup_field, sequence_name=sequence_name)
    model_persistence.import_(
        keep_unmentioned=keep_unmentioned, target_dir=target_dir)


def persistence_filename(scope=None, target_dir=None):
    """Returns the configured persistence file

    :param scope: set to limit by type, i.e. `Organization`
    :param target_dir: set to use non default directory for output

    Using the first value found, looks for an environment variable named
    `PERSISTENCE_DIR`, which should define a path relative to the `portal/config`
    directory such as `eproms`.  If no such environment variable is found, use
    the presence of the `GIL` config setting - if set use `gil`,
    else `eproms`.

    :returns: full path to persistence file

    """
    if scope is None:
        scope = 'site_persistence_file'

    # product level config file - use presence of env var or config setting
    persistence_dir = os.environ.get('PERSISTENCE_DIR')
    gil = current_app.config.get("GIL")

    # prefer env var
    if not persistence_dir:
        persistence_dir = 'gil' if gil else 'eproms'

    filename = os.path.join(
        os.path.dirname(__file__), persistence_dir, '{scope}.json'.format(
            scope=scope))
    if target_dir:
        # Blindly attempt to use target dir if named
        filename = os.path.join(
            target_dir, '{scope}.json'.format(scope=scope))
    elif not os.path.exists(filename):
        raise ValueError(
            'File not found: {}  Check value of environment variable `PERSISTENCE_DIR` '
            'Should be a relative path from portal root.'.format(filename))
    return filename