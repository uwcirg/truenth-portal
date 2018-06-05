"""Unit test module for Notification and UserNotification logic"""
from flask_webtest import SessionScope
from portal.extensions import db
from portal.models.notification import Notification, UserNotification
from tests import TEST_USER_ID, TestCase


class TestNotification(TestCase):
    """Notification and UserNotification tests"""

    def test_notification_from_json(self):
        data = {"name": "test", "content": "Test Alert!"}
        notif = Notification.from_json(data)
        with SessionScope(db):
            db.session.add(notif)
            db.session.commit()
        notif = db.session.merge(notif)

        self.assertTrue(notif.id)
        self.assertTrue(notif.created_at)

    def test_notification_get(self):
        notif = Notification(name="test", content="Test Alert!")
        with SessionScope(db):
            db.session.add(notif)
            db.session.commit()
        notif = db.session.merge(notif)

        un = UserNotification(user_id=TEST_USER_ID, notification_id=notif.id)
        with SessionScope(db):
            db.session.add(un)
            db.session.commit()

        self.login()
        resp = self.client.get(
            '/api/user/{}/notification'.format(TEST_USER_ID))
        self.assert200(resp)

        self.assertEquals(len(resp.json['notifications']), 1)
        self.assertEquals(resp.json['notifications'][0]['name'], 'test')
        self.assertTrue(resp.json['notifications'][0]['created_at'])

    def test_usernotification_delete(self):
        notif = Notification(name="test", content="Test Alert!")
        with SessionScope(db):
            db.session.add(notif)
            db.session.commit()
        notif = db.session.merge(notif)
        notif_id = notif.id

        un = UserNotification(user_id=TEST_USER_ID, notification_id=notif_id)
        with SessionScope(db):
            db.session.add(un)
            db.session.commit()
        notif, un, self.test_user = map(
            db.session.merge, (notif, un, self.test_user))

        self.assertTrue(notif in self.test_user.notifications)

        self.login()
        resp = self.client.delete(
            '/api/user/{}/notification/{}'.format(TEST_USER_ID, notif_id))
        self.assert200(resp)

        # confirm the UserNotification was deleted
        self.assertFalse(notif in self.test_user.notifications)
        self.assertFalse(UserNotification.query.filter_by(
            user_id=TEST_USER_ID, notification_id=notif_id).first())

        # confirm the Notification was NOT deleted
        self.assertTrue(Notification.query.filter_by(name="test").first())
