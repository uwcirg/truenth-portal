"""Unit test module for terms of use logic"""
import json
from flask_webtest import SessionScope
from tempfile import NamedTemporaryFile
from StringIO import StringIO

from tests import TestCase, TEST_USER_ID
from portal.extensions import db
from portal.models.user_document import UserDocument


class TestUserDocument(TestCase):
    """User Document tests"""

    def test_post_patient_report(self):
        #tests whether we can successfully post a patient report -type user doc file
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)
        tmpfile = NamedTemporaryFile(suffix='.pdf')
        tmpfileIO = StringIO(tmpfile.read())
        rv = self.app.post('/api/user/{}/patient_report'.format(service_user.id),
            content_type='multipart/form-data', 
            data=dict({'file': (tmpfileIO, tmpfile.name)}))
        self.assert200(rv)
        tmpfile.close()
