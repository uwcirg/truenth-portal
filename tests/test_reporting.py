"""Unit test module for stat reporting"""
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask_webtest import SessionScope
from re import search

from portal.dogpile import dogpile_cache
from portal.extensions import db
from portal.models.encounter import Encounter
from portal.models.organization import Organization
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.questionnaire_bank import QuestionnaireBankQuestionnaire
from portal.models.reporting import get_reporting_stats, overdue_stats_by_org
from portal.models.reporting import generate_overdue_table_html
from portal.models.research_protocol import ResearchProtocol
from portal.models.role import ROLE
from tests import TestCase


class TestReporting(TestCase):
    """Reporting tests"""

    def test_reporting_stats(self):
        user1 = self.add_user('test1')
        user2 = self.add_user('test2')
        user3 = self.add_user('test3')
        org = Organization(name='testorg')

        with SessionScope(db):
            db.session.add(org)
            user1.organizations.append(org)
            user2.organizations.append(org)
            map(db.session.add, (user1, user2, user3))
            db.session.commit()
        user1, user2, user3, org = map(db.session.merge,
                                       (user1, user2, user3, org))
        userid = user1.id

        self.promote_user(user=user1, role_name=ROLE.PATIENT)
        self.promote_user(user=user2, role_name=ROLE.PATIENT)
        self.promote_user(user=user3, role_name=ROLE.PATIENT)
        self.promote_user(user=user2, role_name=ROLE.PARTNER)
        self.promote_user(user=user3, role_name=ROLE.STAFF)

        with SessionScope(db):
            for i in range(5):
                enc = Encounter(
                    status='finished',
                    auth_method='password_authenticated',
                    start_time=datetime.utcnow(),
                    user_id=userid)
                db.session.add(enc)
            db.session.commit()

        # invalidate cache before testing
        dogpile_cache.invalidate(get_reporting_stats)
        stats = get_reporting_stats()

        self.assertEqual(stats['organizations']['testorg'], 2)
        self.assertEqual(stats['organizations']['Unspecified'], 2)

        self.assertEqual(stats['roles']['patient'], 3)
        self.assertEqual(stats['roles']['staff'], 1)
        self.assertEqual(stats['roles']['partner'], 1)

        self.assertEqual(len(stats['encounters']['all']), 5)

        # test adding a new encounter, to confirm still using cached stats
        with SessionScope(db):
            enc = Encounter(
                status='finished',
                auth_method='password_authenticated',
                start_time=datetime.utcnow(),
                user_id=userid)
            db.session.add(enc)
            db.session.commit()

        stats2 = get_reporting_stats()

        # shold not have changed, if still using cached values
        self.assertEqual(len(stats2['encounters']['all']), 5)

    def test_overdue_stats(self):
        rp = ResearchProtocol(name='proto')
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        crv = Organization(name='CRV', research_protocol_id=rp_id)
        epic26 = Questionnaire(name='epic26')
        with SessionScope(db):
            db.session.add(crv)
            db.session.add(epic26)
            db.session.commit()
        crv, epic26 = map(db.session.merge, (crv, epic26))

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
        self.consent_with_org(org_id=crv.id, backdate=relativedelta(days=18))
        with SessionScope(db):
            db.session.add(bank)
            db.session.commit()
        crv, self.test_user = map(db.session.merge, (crv, self.test_user))

        ostats = overdue_stats_by_org()

        self.assertEqual(len(ostats), 1)
        self.assertEqual(ostats[crv], [15])

    def test_overdue_table_html(self):
        org = Organization(name='testorg')
        false_org = Organization(name='falseorg')

        user = self.add_user('test_user)')

        with SessionScope(db):
            db.session.add(org)
            db.session.add(false_org)
            user.organizations.append(org)
            user.organizations.append(false_org)
            db.session.add(user)
            db.session.commit()
        org, false_org, user = map(db.session.merge,
                                   (org, false_org, user))

        ostats = {org: [1, 8, 9, 11]}
        cutoffs = [5, 10]

        table1 = generate_overdue_table_html(cutoff_days=cutoffs,
                                             overdue_stats=ostats,
                                             user=user,
                                             top_org=org)

        self.assertTrue('<table>' in table1)
        self.assertTrue('<th>1-5 Days</th>' in table1)
        self.assertTrue('<th>6-10 Days</th>' in table1)
        self.assertTrue('<td>{}</td>'.format(org.name) in table1)
        orgrow = (r'<td>{}<\/td>\s*<td>1<\/td>\s*'
                  '<td>2<\/td>\s*<td>3<\/td>'.format(org.name))
        self.assertTrue(search(orgrow, table1))

        # confirm that the table contains no orgs
        table2 = generate_overdue_table_html(cutoff_days=cutoffs,
                                             overdue_stats=ostats,
                                             user=user,
                                             top_org=false_org)

        self.assertTrue('<table>' in table2)
        # org should not show up, as the table's top_org=false_org
        self.assertFalse('<td>{}</td>'.format(org.name) in table2)
        # false_org should not show up, as it's not in the ostats
        self.assertFalse('<td>{}</td>'.format(false_org.name) in table2)
