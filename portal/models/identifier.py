"""Identifier Model Module"""

from ..extensions import db
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM


identifier_use = ENUM('usual', 'official', 'temp', 'secondary',
                      name='id_use', create_type=False)


class Identifier(db.Model):
    """Identifier ORM, for FHIR Identifier resources"""
    __tablename__ = 'identifiers'
    id = db.Column(db.Integer, primary_key=True)
    use = db.Column('id_use', identifier_use)
    system = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text, nullable=False)
    assigner = db.Column(db.String(255))

    __table_args__ = (UniqueConstraint('system', 'value',
        name='_identifier_system_value'),)

    @classmethod
    def from_fhir(cls, data):
        instance = cls()
        # if we aren't given a 'use', call it 'usual'
        instance.use = data['use'] if 'use' in data else 'usual'
        instance.system = data['system']
        instance.value = data['value']
        if 'assigner' in data:
            instance.assigner = data['assigner']
        return instance

    def __str__(self):
        return 'Identifier {0.use} {0.system} {0.value}'.format(self)

    def as_fhir(self):
        d = {}
        for k in ('use', 'system', 'value', 'assigner'):
            if hasattr(self, k):
                d[k] = getattr(self, k)
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, matching on **system** and **value** alone.
        Note the database unique constraint to match.

        @return: the new or matched Identifier

        """
        existing = Identifier.query.filter_by(system=self.system,
                                              value=self.value).first()
        if not existing:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        else:
            self.id = existing.id
        self = db.session.merge(self)
        return self

