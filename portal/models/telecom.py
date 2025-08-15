"""Telecom Module

FHIR uses a telecom structure for email, fax, phone, etc.

"""
from flask import current_app
from sqlalchemy import Enum

from ..database import db

cp_sys_list = ['phone', 'fax', 'email', 'pager', 'url', 'sms', 'other']
cp_use_list = ['home', 'work', 'temp', 'old', 'mobile']

contactpoint_sys = Enum(*cp_sys_list, name='cp_sys', create_type=False)
contactpoint_use = Enum(*cp_use_list, name='cp_use', create_type=False)


class ContactPoint(db.Model):
    """ContactPoint model for storing FHIR telecom entries"""

    __tablename__ = 'contact_points'
    id = db.Column(db.Integer, primary_key=True)
    system = db.Column('cp_sys', contactpoint_sys, nullable=False)
    use = db.Column('cp_use', contactpoint_use)
    value = db.Column(db.Text)
    rank = db.Column(db.Integer)

    def __str__(self):
        return "contactpoint {0.id}".format(self)

    @classmethod
    def from_fhir(cls, data):
        cp = cls()
        return cp.update_from_fhir(data)

    def update_from_fhir(self, data):
        if 'system' in data:
            self.system = data['system']
        if 'use' in data:
            self.use = data['use']
        if 'value' in data:
            self.value = data['value']
        if 'rank' in data:
            self.rank = data['rank']
        return self

    def as_fhir(self):
        d = {}
        d['system'] = self.system
        d['use'] = self.use
        d['value'] = self.value
        if self.rank:
            d['rank'] = self.rank
        return d


class Telecom(object):
    """Telecom model - not a formal db front at this time

    Several FHIR resources include telecom entries.  This helper
    class wraps common functions.

    """

    def __init__(self, email=None, contact_points=None):
        self.email = email
        self.contact_points = contact_points or []

    def __str__(self):
        return "Telecom: {0.email} {0.contact_points}".format(self)

    @classmethod
    def from_fhir(cls, data):
        telecom = cls()
        for item in data:
            system = item.get('system')
            value = item.get('value')
            use = item.get('use')
            if system not in cp_sys_list:
                current_app.logger.warning(
                    "FHIR contains unexpected telecom system {system}"
                    " ignoring {value}".format(**item))
            elif use and use not in cp_use_list:
                current_app.logger.warning(
                    "FHIR contains unexpected telecom use {use}"
                    " ignoring {value}".format(**item))
            elif any(
                (cp.system == system and cp.use == use)
                for cp in telecom.contact_points
            ):
                current_app.logger.warning(
                    "FHIR contains multiple telecom entries for "
                    "{system} ignoring {value}".format(**item))
            else:
                if system == 'email':
                    telecom.email = value
                telecom.contact_points.append(ContactPoint.from_fhir(item))
        return telecom

    def as_fhir(self):
        telecom = []
        if self.email:
            telecom.append({'system': 'email',
                            'value': self.email})
        for cp in self.contact_points:
            if cp:
                fhir = cp.as_fhir()
                if 'value' in fhir:
                    telecom.append(fhir)
        return telecom

    def cp_dict(self):
        telecom = {}
        for cp in self.contact_points:
            if cp:
                telecom[(cp.system, cp.use)] = cp.value
        return telecom
