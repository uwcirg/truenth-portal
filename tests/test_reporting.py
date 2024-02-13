"""Unit test module for stat reporting"""

from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask_webtest import SessionScope

from portal.cache import cache
from portal.extensions import db
from portal.models.encounter import EC
from portal.models.organization import Organization
from portal.models.overall_status import OverallStatus
from portal.models.qb_status import QB_Status
from portal.models.qb_timeline import invalidate_users_QBT
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
    QuestionnaireBankQuestionnaire,
    trigger_date
)
from portal.models.reporting import cache_adherence_data
from portal.models.research_protocol import ResearchProtocol
from portal.models.role import ROLE
from portal.system_uri import TRUENTH_EXTERNAL_STUDY_SYSTEM
from portal.timeout_lock import ADHERENCE_DATA_KEY, CacheModeration
from tests import TEST_USER_ID, TestCase, associative_backdate
from tests.test_assessment_status import mock_qr
from tests.test_questionnaire_bank import TestQuestionnaireBankFixture


class TestReporting(TestCase):
    """Reporting tests"""

    def get_ostats(self, invalidate=True):
        """Cache free access for testing"""
        from portal.models.reporting import overdue_stats_by_org
        if invalidate:
            cache.delete("overdue_stats_by_org")
        return overdue_stats_by_org()

    def test_overdue_stats(self):
        self.promote_user(user=self.test_user, role_name=ROLE.PATIENT.value)
        self.test_user = db.session.merge(self.test_user)
        self.add_user_identifier(
            user=self.test_user, system=TRUENTH_EXTERNAL_STUDY_SYSTEM,
            value='clever study id')
        self.add_system_user()

        rp = ResearchProtocol(name='proto', research_study_id=0)
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        crv = Organization(name='CRV')
        crv.research_protocols.append(rp)
        epic26 = self.add_questionnaire(name='epic26')
        with SessionScope(db):
            db.session.add(crv)
            db.session.commit()
        crv, epic26 = map(db.session.merge, (crv, epic26))
        crv_id = crv.id

        bank = QuestionnaireBank(
            name='CRV', research_protocol_id=rp_id,
            start='{"days": 1}',
            overdue='{"days": 2}',
            expired='{"days": 90}')
        qbq = QuestionnaireBankQuestionnaire(
            questionnaire_id=epic26.id,
            rank=0)
        bank.questionnaires.append(qbq)

        with SessionScope(db):
            db.session.add(bank)
            db.session.commit()

        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)
        self.consent_with_org(org_id=crv_id)
        self.test_user = db.session.merge(self.test_user)

        # test user with status = 'Expired' (should not show up)
        a_s = QB_Status(
            self.test_user, research_study_id=0, as_of_date=datetime.utcnow())
        assert a_s.overall_status == OverallStatus.expired

        ostats = self.get_ostats()
        assert len(ostats) == 0

        # test user with status = 'Overdue' (should show up)
        self.consent_with_org(org_id=crv_id, backdate=relativedelta(days=18))
        with SessionScope(db):
            db.session.add(bank)
            db.session.commit()
        crv, self.test_user = map(db.session.merge, (crv, self.test_user))

        cache.delete_memoized(trigger_date)
        invalidate_users_QBT(self.test_user.id, research_study_id='all')
        a_s = QB_Status(
            self.test_user, research_study_id=0, as_of_date=datetime.utcnow())
        assert a_s.overall_status == OverallStatus.overdue

        ostats = self.get_ostats()
        assert len(ostats) == 1
        row = ostats[(crv.id, crv.name)][0]
        assert len(row) == 5
        assert row[0] == TEST_USER_ID
        assert row[1] == 'clever study id'
        assert row[2] == 'Baseline'
        assert row[3] == a_s.due_date
        assert row[4] == a_s.expired_date


class TestQBStats(TestQuestionnaireBankFixture):

    def test_empty(self):
        self.promote_user(role_name=ROLE.STAFF.value)
        self.login()
        response = self.results_from_async_call(
            "/api/report/questionnaire_status")
        assert response.json['resourceType'] == 'Bundle'
        assert response.json['total'] == 0

    def test_protected_results(self):
        self.promote_user(role_name=ROLE.STAFF.value)
        self.login()
        task_path, response = self.results_from_async_call(
            "/api/report/questionnaire_status", include_task_path=True)

        # login as different user and attempt to access results
        second_user = self.add_user('second_user')
        self.login(second_user.id)
        response = self.client.get(task_path)
        assert response.status_code == 401
        assert not response.json

    def test_adherence_sort(self):
        from portal.models.adherence_data import sort_by_visit_key
        sort_me = {
            "Month 3": {
                "qb": "CRV_recurring_3mo_period v2",
                "site": "CRV",
                "visit": "Month 3",
                "status": "Completed",
                "consent": "11 - Mar - 2023 07: 42: 46 ",
                "country ": None,
                "user_id": 4,
                "site_code": "",
                "entry_method": "interview_assisted",
                "completion_date ": "19 - Jun - 2023 07: 42:46 ",
                "oow_completion_date": ""
            },
            "Month 12 post-withdrawn": {
                "qb": "CRV Baseline v2",
                "site": "CRV",
                "visit": "Month 12",
                "status": "Completed",
                "consent": "20 - May - 2023 07: 42:46 ",
                "completion_date ": "25 - Jun - 2023 00:00:00 ",
                "country ": None,
                "user_id ": 3,
                "study_id": "study user 3",
                "site_code": ""},
            "Month 12": {
                "qb": "CRV Baseline v2",
                "site": "CRV",
                "status": "Withdrawn",
                "completion_date ": "22 - Jun - 2023 00:00:00 ",
                "consent": "20 - May - 2023 07: 42:46 ",
                "country ": None,
                "user_id ": 3,
                "study_id": "study user 3",
                "site_code": ""},
            "Baseline": {
                "qb": "CRV Baseline v2",
                "site": "CRV",
                "visit": "Baseline",
                "status": "Due",
                "consent": "19 - Jun - 2023 07: 42:46",
                "country ": None,
                "user_id ": 2,
                "study_id": "study user 2",
                "site_code": ""
            },
        }
        results = sort_by_visit_key(sort_me)
        assert len(results) == 4
        assert results[0]["visit"] == "Baseline"
        assert results[1]["visit"] == "Month 3"
        assert results[2]["status"] == "Withdrawn"
        assert results[3]["status"] == "Completed"

    def populate_adherence_cache(self, test_users):
        """helper method to bring current test user state into adherence cache"""
        self.add_system_user()
        for u in test_users:
            u = db.session.merge(u)
            cache_moderation = CacheModeration(key=ADHERENCE_DATA_KEY.format(
                patient_id=u.id, research_study_id=0))
            cache_moderation.reset()
            cache_adherence_data(patient_id=u.id)

    def test_permissions(self):
        """Shouldn't get results from orgs outside view permissions"""

        # Generate a few patients from different orgs
        org1_name, org2_name = 'test_org1', 'test_org2'
        org1 = Organization(name=org1_name)
        org2 = Organization(name=org2_name)
        with SessionScope(db):
            db.session.add(org1)
            db.session.add(org2)
            db.session.commit()
        org1 = db.session.merge(org1)
        org1_id = org1.id
        self.setup_org_qbs(org1)
        org2 = db.session.merge(org2)
        self.setup_org_qbs(org2)

        user2 = self.add_user('user2')
        user3 = self.add_user('user3')
        user4 = self.add_user('user4')
        with SessionScope(db):
            db.session.add(user2)
            db.session.add(user3)
            db.session.add(user4)
            db.session.commit()
        user2 = db.session.merge(user2)
        user3 = db.session.merge(user3)
        user4 = db.session.merge(user4)

        now = datetime.utcnow()
        back15, nowish = associative_backdate(now, relativedelta(days=15))
        back45, nowish = associative_backdate(now, relativedelta(days=45))
        back115, nowish = associative_backdate(now, relativedelta(days=115))
        self.bless_with_basics(
            user=user2, setdate=back15, local_metastatic=org1_name)
        self.bless_with_basics(
            user=user3, setdate=back45, local_metastatic=org1_name)
        self.bless_with_basics(
            user=user4, setdate=back115, local_metastatic=org2_name)

        self.test_user = db.session.merge(self.test_user)
        self.promote_user(role_name=ROLE.STAFF.value)
        self.login()
        self.populate_adherence_cache(test_users=(user2, user3, user4))
        response = self.results_from_async_call(
            "/api/report/questionnaire_status", timeout=10)

        # with zero orgs in common, should see empty result set
        assert response.json['total'] == 0

        self.populate_adherence_cache(test_users=(self.test_user, user2, user3, user4))

        # Add org to staff to see results from matching patients (2&3)
        self.consent_with_org(org_id=org1_id)
        response = self.results_from_async_call(
            "/api/report/questionnaire_status", timeout=10)
        assert response.json['total'] == 2

    def test_results(self):
        # Generate a few patients with differing results
        org = self.setup_org_qbs()
        org_id, org_name = org.id, org.name
        user2 = self.add_user('user2')
        user3 = self.add_user('user3')
        user4 = self.add_user('user4')
        with SessionScope(db):
            db.session.add(user2)
            db.session.add(user3)
            db.session.add(user4)
            db.session.commit()
        user2 = db.session.merge(user2)
        user3 = db.session.merge(user3)
        user4 = db.session.merge(user4)
        user4_id = user4.id

        self.add_user_identifier(
            user=user2, system=TRUENTH_EXTERNAL_STUDY_SYSTEM,
            value='study user 2')
        self.add_user_identifier(
            user=user3, system=TRUENTH_EXTERNAL_STUDY_SYSTEM,
            value='study user 3')

        now = datetime.utcnow()
        back15, nowish = associative_backdate(now, relativedelta(days=15))
        back45, nowish = associative_backdate(now, relativedelta(days=45))
        back115, nowish = associative_backdate(now, relativedelta(days=115))
        self.bless_with_basics(
            user=user2, setdate=back15, local_metastatic=org_name)
        self.bless_with_basics(
            user=user3, setdate=back45, local_metastatic=org_name)
        self.bless_with_basics(
            user=user4, setdate=back115, local_metastatic=org_name)

        # submit a mock response for all q's in 3 mo qb
        # which should result in completed status for user4
        qb_name = "CRV_recurring_3mo_period v2"
        threeMo = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()

        for q in threeMo.questionnaires:
            q = db.session.merge(q)
            mock_qr(
                q.name, qb=threeMo, iteration=0, user_id=user4_id,
                timestamp=back15, entry_method=EC.INTERVIEW_ASSISTED)

        self.test_user = db.session.merge(self.test_user)
        self.promote_user(role_name=ROLE.STAFF.value)
        self.consent_with_org(org_id=org_id)
        self.login()
        self.populate_adherence_cache(test_users=(user2, user3, user4))
        response = self.results_from_async_call(
            "/api/report/questionnaire_status", timeout=10)

        # expect baseline for each plus 3 mo for user4
        assert response.json['total'] == 4
        expect = {'Due', 'Overdue', 'Completed', 'Expired'}
        found = set([item['status'] for item in response.json['entry']])
        assert expect == found
        # the one done should have entry method set above
        for item in response.json['entry']:
            if item['status'] == 'Completed':
                assert item['entry_method'] == 'interview_assisted'
            else:
                assert 'entry_method' not in item
