"""Unit test module for terms of use logic"""
import json
from flask_webtest import SessionScope

from tests import TestCase, TEST_USER_ID
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.tou import ToU


class TestTou(TestCase):
    """Terms Of Use tests"""

    def test_tou_str(self):
        audit = Audit(user_id=TEST_USER_ID, comment="Agreed to ToU")
        tou = ToU(audit=audit, text="Your data is safe, trust us")
        results = "{}".format(tou)
        self.assertTrue('Your data is safe' in results)

    def test_accept(self):
        tou_text = """Lorem ipsum dolor sit amet, consectetur adipiscing elit.
        Sed gravida, urna sed faucibus laoreet, turpis sapien euismod turpis, a
        feugiat velit neque sed ligula. Sed magna risus, tincidunt a mauris ut,
        finibus ultricies justo. Phasellus lobortis, dui fringilla dignissim
        ornare, risus augue pharetra odio, ac vulputate lacus leo at odio.
        Donec lobortis pellentesque dapibus. Quisque et convallis elit, in
        placerat nibh. Donec ac lacus eu justo lobortis sollicitudin vel eget
        mi. Morbi placerat egestas elit sit amet tempus. Nam sodales mattis
        nisi gravida dignissim.

        Donec sed odio quis justo porttitor auctor. Aliquam nisl enim, faucibus
        eget tristique non, tincidunt eget neque. Suspendisse in ex eu sem
        ultricies euismod vel dapibus lorem. Vivamus tortor metus, laoreet
        vulputate ornare eu, lacinia et enim. Duis sodales, mi scelerisque
        laoreet egestas, dui enim commodo ex, in posuere magna nisi eu lacus.
        Integer id libero in enim volutpat auctor. Proin sed lacinia lacus.
        Nulla facilisi. Nulla facilisi. Integer purus diam, gravida quis neque
        sit amet, laoreet imperdiet risus."""

        self.login()
        data = {'text': tou_text}
        rv = self.app.post('/api/tou/accepted',
                           content_type='application/json',
                           data=json.dumps(data))
        self.assert200(rv)
        tou = ToU.query.one()
        self.assertEquals(tou.text, tou_text)
        self.assertEquals(tou.audit.user_id, TEST_USER_ID)

    def test_get(self):
        audit = Audit(user_id=TEST_USER_ID)
        tou = ToU(audit=audit, text='terms text')
        with SessionScope(db):
            db.session.add(tou)
            db.session.commit()

        self.login()
        rv = self.app.get('/api/user/{}/tou'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(rv.json['accepted'], True)
