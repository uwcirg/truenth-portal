"""Research Protocol module"""
from datetime import datetime

from ..database import db
from ..date_tools import FHIR_datetime


class ResearchProtocol(db.Model):
    """ResearchProtocol model for tracking QB versions"""
    __tablename__ = 'research_protocols'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow)
    research_study_id = db.Column(
        db.ForeignKey('research_studies.id', ondelete='cascade'),
        index=True, nullable=False)

    @classmethod
    def from_json(cls, data):
        if 'name' not in data:
            raise ValueError("missing required name field")
        instance = cls()
        return instance.update_from_json(data)

    def update_from_json(self, data):
        self.name = data['name']
        self.research_study_id = data['research_study_id']
        if 'created_at' in data:
            self.created_at = FHIR_datetime.parse(data['created_at'])
        return self

    def as_json(self):
        return {
            'id': self.id,
            'resourceType': 'ResearchProtocol',
            'name': self.name,
            'display_name': self.display_name,
            'research_study_id': self.research_study_id,
            'created_at': FHIR_datetime.as_fhir(self.created_at)}

    @property
    def display_name(self):
        """Generate and return 'Title Case' version of name 'title_case' """
        if not self.name:
            return
        word_list = self.name.split('_')
        return ' '.join([n.title() for n in word_list])

    @staticmethod
    def assigned_to(user, research_study_id):
        """Returns set of tuples (ResearchProtocol, retired) for user"""
        rps = set()
        for org in user.organizations:
            for r in org.rps_w_retired(
                    research_study_id, consider_parents=True):
                rps.add(r)
        return rps
