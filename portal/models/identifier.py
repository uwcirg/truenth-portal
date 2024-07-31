"""Identifier Model Module"""
from builtins import str
import json

from sqlalchemy import Enum, UniqueConstraint
from werkzeug.exceptions import BadRequest, Conflict

from ..database import db
from ..system_uri import TRUENTH_EXTERNAL_STUDY_SYSTEM

identifier_use = Enum('usual', 'official', 'temp', 'secondary',
                      name='id_use', create_type=False)
UNIQUE_IDENTIFIER_SYSTEMS = {TRUENTH_EXTERNAL_STUDY_SYSTEM}


class Identifier(db.Model):
    """Identifier ORM, for FHIR Identifier resources"""
    __tablename__ = 'identifiers'
    id = db.Column(db.Integer, primary_key=True)
    use = db.Column('id_use', identifier_use)
    system = db.Column(db.String(255), nullable=False)
    _value = db.Column('value', db.Text, nullable=False)
    assigner = db.Column(db.String(255))

    __table_args__ = (UniqueConstraint(
        'system', 'value', name='_identifier_system_value'),)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        # Force to text
        self._value = str(value)
        # Don't allow empty string
        if not len(self._value):
            raise TypeError("<empty string>")

    @classmethod
    def from_fhir(cls, data):
        if not data or not all((data.get('system'), data.get('value'))):
            raise ValueError(
                "Ill formed 'identifier'; requires both 'system' and "
                "'value' to unambiguously define resource")

        instance = cls()
        # if we aren't given a 'use', call it 'usual'
        instance.use = data['use'] if 'use' in data else 'usual'
        instance.system = data['system']
        instance.value = data['value']
        # FHIR changed - assigner needs to reference object in system
        # not storing at this time
        # if 'assigner' in data:
        #    instance.assigner = data['assigner']
        return instance

    def __str__(self):
        return 'Identifier {0.use} {0.system} {0.value}'.format(self)

    def __key(self):
        # Only use (system, value), as per unique constraint
        return (self.system, self.value)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()

    def as_fhir(self):
        d = {}
        for k in ('use', 'system', 'value', 'assigner'):
            if getattr(self, k, None):
                d[k] = getattr(self, k)
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, matching on **system** and **value** alone.
        Note the database unique constraint to match.

        @return: the new or matched Identifier

        """
        existing = Identifier.query.filter_by(system=self.system,
                                              _value=self.value).first()
        if not existing:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        else:
            self.id = existing.id
        self = db.session.merge(self)
        return self


class UserIdentifier(db.Model):
    """ORM class for user_identifiers data

    Holds links to any additional identifiers a user may have,
    such as study participation.

    """
    __tablename__ = 'user_identifiers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    identifier_id = db.Column(
        db.ForeignKey('identifiers.id'), nullable=False)
    identifier = db.relationship(Identifier, cascade="save-update")
    user = db.relationship('User', cascade="save-update")

    __table_args__ = (UniqueConstraint(
        'user_id', 'identifier_id', name='_user_identifier'),)

    def __str__(self):
        return ("user_identifier {} for {}".format(
            self.identifier, self.user))

    @staticmethod
    def check_unique(user, identifier):
        """Raises 409 if given identifier should be unique but is in use

        UserIdentifiers are not all unique - depends on the system, namely
        if the system is part of ``UNIQUE_IDENTIFIER_SYSTEMS``.  For
        example, the region system identifiers are often shared with many
        users.  Others are treated as unique, such as study-id, and therefore
        raise exceptions if already in use (that is, when the given identifier
        is already associated with a user other than the named parameter).

        :param identifier: identifier to check, or ignore if system isn't
          treated as unique
        :param user: intended recipient

        :raises: UniqueConstraint if identifier's system is in
          UNIQUE_IDENTIFIER_SYSTEMS and the identifier is assigned
          to another, not deleted, user.
        :returns: True - exception thrown if unique "constraint" broken.

        """
        from .user import User

        if identifier.system in UNIQUE_IDENTIFIER_SYSTEMS:
            existing = UserIdentifier.query.join(User).filter(
                UserIdentifier.identifier_id == identifier.id).filter(
                UserIdentifier.user_id != user.id).filter(
                User.deleted_id.is_(None))
            if existing.count():
                raise Conflict(
                    "Unique {} already in use; can't assign to {}".format(
                        identifier, user))
        return True


def parse_identifier_params(arg):
    """Parse identifier parameter from given arg

    Supports FHIR pipe delimited system|value or legacy FHIR JSON named
    parameters {'system', 'value'}

    :param arg: argument string, may be serialized JSON or pipe delimited
    :raises: BadRequest if unable to parse valid system, value
    :returns: (system, value) tuple

    """
    if arg is None:
        raise BadRequest("Missing required identifier parameter")

    if '|' in arg:
        system, value = arg.split('|')
    else:
        try:
            ident_dict = json.loads(arg)
            system = ident_dict.get('system')
            value = ident_dict.get('value')
        except ValueError:
            raise BadRequest("Ill formed identifier parameter")
    return system, value
