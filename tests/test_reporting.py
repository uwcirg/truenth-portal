"""Unit test module for stat reporting"""

from datetime import datetime
from re import search
from time import sleep

from dateutil.relativedelta import relativedelta
from flask_webtest import SessionScope

from portal.dogpile_cache import dogpile_cache
from portal.extensions import db
from portal.models.encounter import EC, Encounter
from portal.models.intervention import INTERVENTION
from portal.models.organization import Organization
from portal.models.overall_status import OverallStatus
from portal.models.qb_status import QB_Status
from portal.models.qb_timeline import invalidate_users_QBT
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
    QuestionnaireBankQuestionnaire,
)
from portal.models.research_protocol import ResearchProtocol
from portal.models.role import ROLE
from portal.views.reporting import generate_overdue_table_html
from tests import TEST_USER_ID, TestCase, associative_backdate
from tests.test_assessment_status import mock_qr
from tests.test_questionnaire_bank import TestQuestionnaireBank


class TestReporting(TestCase):
    """Reporting tests"""

    def get_stats(self, invalidate=True):
        """Cache free access for testing"""
        from portal.models.reporting import get_reporting_stats
        if invalidate:
            dogpile_cache.invalidate(get_reporting_stats)
        return get_reporting_stats()

    def get_ostats(self, invalidate=True):
        """Cache free access for testing"""
        from portal.models.reporting import overdue_stats_by_org
        if invalidate:
            dogpile_cache.invalidate(overdue_stats_by_org)
        return overdue_stats_by_org()

    def test_reporting_stats(self):
        user1 = self.add_user('test1')
        user2 = self.add_user('test2')
        user3 = self.add_user('test3')
        org = Organization(name='testorg')
        interv1 = INTERVENTION.COMMUNITY_OF_WELLNESS
        interv2 = INTERVENTION.DECISION_SUPPORT_P3P
        interv1.public_access = False
        interv2.public_access = True

        user1, user2, user3 = map(
            db.session.merge, (user1, user2, user3))
        with SessionScope(db):
            db.session.add(org)
            db.session.add(interv1)
            db.session.add(interv2)
            user1.organizations.append(org)
            user2.organizations.append(org)
            user2.interventions.append(interv1)
            user3.interventions.append(interv2)
            map(db.session.add, (user1, user2, user3))
            db.session.commit()
        user1, user2, user3, org = map(db.session.merge,
                                       (user1, user2, user3, org))
        userid = user1.id

        self.promote_user(user=user1, role_name=ROLE.PATIENT.value)
        self.promote_user(user=user2, role_name=ROLE.PATIENT.value)
        self.promote_user(user=user3, role_name=ROLE.PATIENT.value)
        self.promote_user(user=user2, role_name=ROLE.PARTNER.value)
        self.promote_user(user=user3, role_name=ROLE.STAFF.value)

        with SessionScope(db):
            for i in range(5):
                enc = Encounter(
                    status='finished',
                    auth_method='password_authenticated',
                    start_time=datetime.utcnow(),
                    user_id=userid)
                db.session.add(enc)
            db.session.commit()

        stats = self.get_stats()

        assert 'Decision Support P3P' not in stats['interventions']
        assert stats['interventions']['Community of Wellness'] == 1

        assert stats['organizations']['testorg'] == 2
        assert stats['organizations']['Unspecified'] == 2

        assert stats['roles']['patient'] == 3
        assert stats['roles']['staff'] == 1
        assert stats['roles']['partner'] == 1

        assert len(stats['encounters']['all']) == 5

        # test adding a new encounter, to confirm still using cached stats
        with SessionScope(db):
            enc = Encounter(
                status='finished',
                auth_method='password_authenticated',
                start_time=datetime.utcnow(),
                user_id=userid)
            db.session.add(enc)
            db.session.commit()

        stats2 = self.get_stats(invalidate=False)

        # should not have changed, if still using cached values
        assert len(stats2['encounters']['all']) == 5

    def test_overdue_stats(self):
        self.promote_user(user=self.test_user, role_name=ROLE.PATIENT.value)

        rp = ResearchProtocol(name='proto')
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
        a_s = QB_Status(self.test_user, as_of_date=datetime.utcnow())
        assert a_s.overall_status == OverallStatus.expired

        ostats = self.get_ostats()
        assert len(ostats) == 0

        # test user with status = 'Overdue' (should show up)
        self.consent_with_org(org_id=crv_id, backdate=relativedelta(days=18))
        with SessionScope(db):
            db.session.add(bank)
            db.session.commit()
        crv, self.test_user = map(db.session.merge, (crv, self.test_user))

        invalidate_users_QBT(self.test_user.id)
        a_s = QB_Status(self.test_user, as_of_date=datetime.utcnow())
        assert a_s.overall_status == OverallStatus.overdue

        ostats = self.get_ostats()
        assert len(ostats) == 1
        assert ostats[(crv.id, crv.name)] == [(15, TEST_USER_ID)]

    def test_overdue_table_html(self):
        org = Organization(name='OrgC', id=101)
        org2 = Organization(name='OrgB', id=102, partOf_id=101)
        org3 = Organization(name='OrgA', id=103, partOf_id=101)
        false_org = Organization(name='falseorg')

        user = self.add_user('test_user)')

        with SessionScope(db):
            db.session.add(org)
            db.session.add(org3)
            db.session.add(org2)
            db.session.add(false_org)
            user.organizations.append(org)
            user.organizations.append(org3)
            user.organizations.append(org2)
            user.organizations.append(false_org)
            db.session.add(user)
            db.session.commit()
        org, org2, org3, false_org, user = map(
            db.session.merge, (org, org2, org3, false_org, user))

        ostats = {
            (org3.id, org3.name): [(2, 101), (3, 102)],
            (org2.id, org2.name): [(1, 103), (5, 104)],
            (org.id, org.name): [(1, 105), (8, 106), (9, 107), (11, 108)]}
        cutoffs = [5, 10]

        table1 = generate_overdue_table_html(cutoff_days=cutoffs,
                                             overdue_stats=ostats,
                                             user=user,
                                             top_org=org)

        assert '<table>' in table1
        assert '<th>1-5 Days</th>' in table1
        assert '<th>6-10 Days</th>' in table1
        assert '<td>{}</td>'.format(org.name) in table1
        org_row = r'\s*'.join((
            '<td>{}</td>',
            '<td>1</td>',
            '<td>2</td>',
            '<td>3</td>',
        )).format(org.name)
        assert search(org_row, table1)
        # confirm alphabetical order
        org_order = r'{}[^O]*{}[^O]*{}'.format(org3.name, org2.name, org.name)
        assert search(org_order, table1)

        # confirm that the table contains no orgs
        table2 = generate_overdue_table_html(cutoff_days=cutoffs,
                                             overdue_stats=ostats,
                                             user=user,
                                             top_org=false_org)

        assert '<table>' in table2
        # org should not show up, as the table's top_org=false_org
        assert not '<td>{}</td>'.format(org.name) in table2
        # false_org should not show up, as it's not in the ostats
        assert not '<td>{}</td>'.format(false_org.name) in table2


class TestQBStats(TestQuestionnaireBank):

    def results_from_async_call(
            self, url, timeout=5, include_task_path=False):
        """Wrap task of obtaining results from an async request"""
        response = self.client.get(url)
        # expect 202 response with location of status
        assert response.status_code == 202
        status_url = response.headers.get('Location')

        # Give task a number of one second pauses to complete
        for i in range(0, timeout):
            response = self.client.get(status_url)
            if response.json['state'] == 'SUCCESS':
                break
            sleep(1)

        assert response.json['state'] == 'SUCCESS'

        # done, now pull result (chop /status from status url for task result)
        task_path = status_url[:-len('/status')]
        results = self.client.get(task_path)
        if include_task_path:
            return task_path, results
        return results

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
        response = self.results_from_async_call(
            "/api/report/questionnaire_status", timeout=10)

        # with zero orgs in common, should see empty result set
        assert response.json['total'] == 0

        # Add org to staff to see results from matching patiens (2&3)
        self.consent_with_org(org_id=org1_id)
        response = self.results_from_async_call(
            "/api/report/questionnaire_status", timeout=10)
        assert response.json['total'] == 2

    def test_results(self):
        from portal.system_uri import TRUENTH_EXTERNAL_STUDY_SYSTEM

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
