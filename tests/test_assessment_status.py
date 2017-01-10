"""Module to test assessment_status"""
from datetime import datetime
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.fhir import CC, QuestionnaireResponse, assessment_status
from tests import TestCase, TEST_USER_ID


def mock_qr(user_id, instrument_id):
    today = datetime.utcnow()
    qr_document = {
        "questionnaire": {
            "display": "Additional questions",
            "reference":
            "https://{}/api/questionnaires/{}".format(
                'SERVER_NAME', instrument_id)
        }
    }
    qr = QuestionnaireResponse(
        subject_id=TEST_USER_ID, status='completed',
        authored=today,
        document=qr_document)
    with SessionScope(db):
        db.session.add(qr)
        db.session.commit()


class TestAssessment(TestCase):

    def mark_localized(self):
        self.test_user.save_constrained_observation(
            codeable_concept=CC.PCaLocalized, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID))

    def test_localized_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26')

        self.test_user = db.session.merge(self.test_user)
        assessment_status(self.test_user)
        self.assertEquals(assessment_status(self.test_user), "Completed")

    def test_localized_in_process(self):
        # User finished one, time remains for other
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add')

        self.test_user = db.session.merge(self.test_user)
        self.assertEquals(assessment_status(self.test_user), "In Progress")

    def test_metastatic_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        mock_qr(user_id=TEST_USER_ID, instrument_id='eortc')

        self.test_user = db.session.merge(self.test_user)
        self.assertEquals(assessment_status(self.test_user), "Completed")

    def test_metastatic_due(self):
        # hasn't taken, but still in "Due" period
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user = db.session.merge(self.test_user)
        self.assertEquals(assessment_status(self.test_user), "Due")
