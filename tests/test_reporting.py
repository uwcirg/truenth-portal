"""Unit test module for stat reporting"""
from __future__ import unicode_literals  # isort:skip

from datetime import datetime
from re import search

from dateutil.relativedelta import relativedelta
from flask_webtest import SessionScope

from portal.dogpile_cache import dogpile_cache
from portal.extensions import db
from portal.models.assessment_status import AssessmentStatus
from portal.models.encounter import Encounter
from portal.models.intervention import INTERVENTION
from portal.models.organization import Organization
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
    QuestionnaireBankQuestionnaire,
)
from portal.models.research_protocol import ResearchProtocol
from portal.models.role import ROLE
from portal.views.reporting import generate_overdue_table_html
from tests import TestCase


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

        # shold not have changed, if still using cached values
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

        self.test_user.organizations.append(crv)
        self.consent_with_org(org_id=crv_id)
        self.test_user = db.session.merge(self.test_user)

        # test user with status = 'Expired' (should not show up)
        a_s = AssessmentStatus(self.test_user, as_of_date=datetime.utcnow())
        assert a_s.overall_status == 'Expired'

        ostats = self.get_ostats()
        assert len(ostats) == 0

        # test user with status = 'Overdue' (should show up)
        self.consent_with_org(org_id=crv_id, backdate=relativedelta(days=18))
        with SessionScope(db):
            db.session.add(bank)
            db.session.commit()
        crv, self.test_user = map(db.session.merge, (crv, self.test_user))

        a_s = AssessmentStatus(self.test_user, as_of_date=datetime.utcnow())
        assert a_s.overall_status == 'Overdue'

        ostats = self.get_ostats()
        assert len(ostats) == 1
        assert ostats[crv] == [15]

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

        ostats = {org3: [2, 3], org2: [1, 5], org: [1, 8, 9, 11]}
        cutoffs = [5, 10]

        table1 = generate_overdue_table_html(cutoff_days=cutoffs,
                                             overdue_stats=ostats,
                                             user=user,
                                             top_org=org)

        assert '<table>' in table1
        assert '<th>1-5 Days</th>' in table1
        assert '<th>6-10 Days</th>' in table1
        assert '<td>{}</td>'.format(org.name) in table1
        org_row = (r'<td>{}<\/td>\s*<td>1<\/td>\s*'
                   '<td>2<\/td>\s*<td>3<\/td>'.format(org.name))
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
