"""Research Protocol module"""
from datetime import datetime

from ..database import db


class ResearchProtocol(db.Model):
    """ResearchProtocol model for tracking QB versions"""
    __tablename__ = 'research_protocols'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False)

    def __init__(self):
        self.created_at = datetime.utcnow()

    @classmethod
    def from_json(cls, data):
        if 'name' not in data:
            raise ValueError("missing required name field")
        rp = ResearchProtocol.query.filter(name=data['name']).first()
        if not rp:
            rp = cls()
            rp.name = data['name']
        return rp

    def as_json(self):
        d = {}
        d['id'] = self.id
        d['resourceType'] = 'ResearchProtocol'
        d['name'] = self.name
        d['created_at'] = self.created_at
        return d
