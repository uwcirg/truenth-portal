"""Unit test module for stat reporting"""
from datetime import datetime
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.encounter import Encounter
from portal.models.organization import Organization
from portal.models.reporting import get_reporting_stats
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

        stats = get_reporting_stats()

        self.assertEqual(stats['organizations']['testorg'], 2)
        self.assertEqual(stats['organizations']['Unspecified'], 2)

        self.assertEqual(stats['roles']['patient'], 3)
        self.assertEqual(stats['roles']['staff'], 1)
        self.assertEqual(stats['roles']['partner'], 1)

        self.assertEqual(len(stats['encounters']['all']), 5)
