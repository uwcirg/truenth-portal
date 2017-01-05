"""Module to test assessment_status"""
from datetime import datetime
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.fhir import CC, QuestionnaireResponse, assessment_status
from tests import TestCase, TEST_USER_ID


eortc_document = {
"questionnaire": {
    "display": "Additional questions",
    "reference":
    "https://eproms-demo.cirg.washington.edu/api/questionnaires/eortc"
      }
}
epic_document = {
"questionnaire": {
    "display": "Additional questions",
    "reference":
    "https://eproms-demo.cirg.washington.edu/api/questionnaires/epic26"
      }
}
eproms_document = {
"questionnaire": {
    "display": "Additional questions",
    "reference":
    "https://eproms-demo.cirg.washington.edu/api/questionnaires/eproms_add"
      }
}


class TestAssessment(TestCase):

    def mark_localized(self):
        self.test_user.save_constrained_observation(
            codeable_concept=CC.PCaLocalized, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID))

    def test_localized_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        today = datetime.utcnow()
        eproms = QuestionnaireResponse(
            subject_id=TEST_USER_ID, status='completed',
            authored=today,
            document=eproms_document)
        epic = QuestionnaireResponse(
            subject_id=TEST_USER_ID, status='completed',
            authored=today,
            document=epic_document)
        with SessionScope(db):
            db.session.add(eproms)
            db.session.add(epic)
            db.session.commit()

        self.test_user = db.session.merge(self.test_user)
        assessment_status(self.test_user)
        self.assertEquals(assessment_status(self.test_user), "Completed")

    def test_localized_in_process(self):
        # User finished one, time remains for other
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        today = datetime.utcnow()
        eproms = QuestionnaireResponse(
            subject_id=TEST_USER_ID, status='completed',
            authored=today,
            document=eproms_document)
        with SessionScope(db):
            db.session.add(eproms)
            db.session.commit()

        self.test_user = db.session.merge(self.test_user)
        self.assertEquals(assessment_status(self.test_user), "In Progress")

    def test_metastatic_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        eortc = QuestionnaireResponse(
            subject_id=TEST_USER_ID, status='completed',
            authored=datetime.utcnow(),
            document=eortc_document)
        with SessionScope(db):
            db.session.add(eortc)
            db.session.commit()

        self.test_user = db.session.merge(self.test_user)
        self.assertEquals(assessment_status(self.test_user), "Completed")

    def test_metastatic_due(self):
        # hasn't taken, but still in "Due" period
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user = db.session.merge(self.test_user)
        self.assertEquals(assessment_status(self.test_user), "Due")
