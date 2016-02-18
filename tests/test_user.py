"""Unit test module for user model"""
from flask.ext.webtest import SessionScope
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.user import User


class TestUser(TestCase):
    """User model tests"""

    def test_unique_username(self):
        dup = User(username='with number 1')
        try_me = User(username='Anonymous', first_name='with',
                      last_name='number')
        with SessionScope(db):
            db.session.add(dup)
            db.session.add(try_me)
            db.session.commit()
        dup = db.session.merge(dup)
        try_me = db.session.merge(try_me)

        try_me.update_username()
        self.assertNotEquals(try_me.username, 'Anonymous')
        self.assertNotEquals(dup.username, try_me.username)
