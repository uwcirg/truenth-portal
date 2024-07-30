"""Table Preference module"""
from datetime import datetime
import json

from sqlalchemy import Enum, UniqueConstraint

from ..database import db
from ..date_tools import FHIR_datetime

sort_order_types = ('asc', 'desc')
sort_order_types_enum = Enum(
    *sort_order_types, name='sort_order_enum', create_type=False)


class TablePreference(db.Model):
    """Captures user preferences for UI table display

    Capture and store user preferences regarding UI table display
    (e.g. sort field/order, field filter values, etc).

    """
    __tablename__ = 'table_preferences'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    table_name = db.Column(db.Text, nullable=False)
    sort_field = db.Column(db.Text)
    sort_order = db.Column('sort_order', sort_order_types_enum)
    filters = db.Column(db.JSON)
    updated_at = db.Column(db.DateTime)

    __table_args__ = (
        UniqueConstraint(user_id, table_name,
                         name='_user_table_uc'),)

    user = db.relationship('User')

    def __str__(self):
        return ("TablePreference for user {0.user_id} "
                "on table {0.table_name}".format(self))

    def as_json(self):
        d = {}
        d['id'] = self.id
        d['user_id'] = self.user_id
        d['table_name'] = self.table_name
        d['sort_field'] = self.sort_field
        d['sort_order'] = self.sort_order
        d['filters'] = self.filters
        d['updated_at'] = FHIR_datetime.as_fhir(self.updated_at)
        return d

    @classmethod
    def from_json(cls, data):
        for field in ('user_id', 'table_name'):
            if field not in data:
                raise ValueError("missing required {} field".format(field))
        pref = TablePreference.query.filter_by(user_id=data['user_id'],
                                               table_name=data['table_name']
                                               ).first()
        if not pref:
            pref = cls()
            pref.user_id = data['user_id']
            pref.table_name = data['table_name']
        for attr in ('sort_field', 'sort_order', 'filters'):
            if attr in data:
                setattr(pref, attr, data[attr])
        pref.updated_at = datetime.now()
        return pref
