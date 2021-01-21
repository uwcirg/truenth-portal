from sqlalchemy.dialects.postgresql import ENUM

from ..cache import TWO_HOURS, cache
from ..database import db
from .questionnaire_bank import QuestionnaireBank, qbs_by_intervention
from .research_protocol import ResearchProtocol
from .user_consent import consent_withdrawal_dates

BASE_RS_ID = 0
EMPRO_RS_ID = 1

status_types = (
    "active", "administratively-completed", "approved", "closed-to-accrual",
    "closed-to-accrual-and-intervention", "completed", "disapproved",
    "in-review", "temporarily-closed-to-accrual",
    "temporarily-closed-to-accrual-and-intervention", "withdrawn")
status_types_enum = ENUM(
    *status_types, name='research_study_status_enum', create_type=False)


class ResearchStudy(db.Model):
    """Model class for a FHIR ResearchStudy

    Used to mark independent Research Studies
    """
    __tablename__ = 'research_studies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, unique=True, nullable=False)
    status = db.Column(
        'status', status_types_enum, server_default='active', nullable=False)

    def as_fhir(self, include_empties=True):
        d = {}
        d['resourceType'] = 'ResearchStudy'
        d['id'] = self.id
        d['title'] = self.title
        d['status'] = self.status
        return d

    @classmethod
    def from_fhir(cls, data):
        rs = cls()
        return rs.update_from_fhir(data)

    def update_from_fhir(self, data):
        if 'id' in data:
            self.id = int(data.get('id'))
        if 'title' in data:
            self.title = data.get('title')
        if 'status' in data:
            self.status = data.get('status')
        return self

    @staticmethod
    def assigned_to(user):
        """Returns list of all ResearchStudy IDs assigned to given user

        NB: assignment doesn't equate to ready status.  User may have
        since withdrawn or failed to meet necessary business rules such
        as clinician assignments.  For user's current status, see
         ``qb_status.patient_research_study_status()``
        """
        base_study = 0
        results = set()
        iqbs = qbs_by_intervention(user, classification=None)
        if iqbs:
            results.add(base_study)  # Use dummy till system need arises

        for rp, _ in ResearchProtocol.assigned_to(
                user, research_study_id='all'):
            rs_id = rp.research_study_id
            if rs_id is None:
                continue

            # As timeline rebuilds are necessary, withdrawn users
            # count in an `assigned_to` check
            c_date, w_date = consent_withdrawal_dates(user, rs_id)
            if c_date or w_date and rs_id not in results:
                results.add(rs_id)
        return sorted(results)


@cache.memoize(timeout=TWO_HOURS)
def qb_name_map():
    """returns QB.name -> research_study_id map"""
    map = {}
    for qb in QuestionnaireBank.query.all():
        rp_id = qb.research_protocol_id
        if rp_id is None:
            continue

        rs_id = qb.research_protocol.research_study_id
        for q in qb.questionnaires:
            if q.name in map:
                if (map[q.name] != rs_id):
                    raise ValueError(
                        f"Configuration error, {q.name} belongs to multiple "
                        "research studies")
            map[q.name] = rs_id
    return map


def research_study_id_from_questionnaire(questionnaire_name):
    """Reverse lookup research_study_id from a questionnaire_name"""
    return qb_name_map().get(questionnaire_name, 0)


def add_static_research_studies():
    """Seed database with default static research studies

    Idempotent - run anytime to pick up any new relationships in existing dbs

    """
    base = {
      "id": 0,
      "title": "Base Study",
      "status": "active",
      "resourceType": "ResearchStudy"
    }

    rs = ResearchStudy.from_fhir(base)
    if ResearchStudy.query.get(rs.id) is None:
        db.session.add(rs)
