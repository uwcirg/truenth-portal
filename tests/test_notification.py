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

        assert notif.id
        assert notif.created_at

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
        assert resp.status_code == 200

        assert len(resp.json['notifications']) == 1
        assert resp.json['notifications'][0]['name'] == 'test'
        assert resp.json['notifications'][0]['created_at']

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

        assert notif in self.test_user.notifications

        self.login()
        resp = self.client.delete(
            '/api/user/{}/notification/{}'.format(TEST_USER_ID, notif_id))
        assert resp.status_code == 200

        # confirm the UserNotification was deleted
        assert notif not in self.test_user.notifications
        assert not UserNotification.query.filter_by(
            user_id=TEST_USER_ID, notification_id=notif_id).first()

        # confirm the Notification was NOT deleted
        assert Notification.query.filter_by(name="test").first()
