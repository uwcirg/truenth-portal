"""Unit test module for user document logic"""
from flask_webtest import SessionScope
from tempfile import NamedTemporaryFile
from StringIO import StringIO
from flask import current_app
import os

from tests import TestCase, TEST_USER_ID
from portal.extensions import db
from portal.models.user_document import UserDocument


class TestUserDocument(TestCase):
    """User Document tests"""

    def test_post_patient_report(self):
        #tests whether we can successfully post a patient report -type user doc file
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)
        test_contents = "This is a test."
        with NamedTemporaryFile(
            prefix='udoc_test_',
            suffix='.pdf',
            delete=True,
        ) as temp_pdf:
            temp_pdf.write(test_contents)
            temp_pdf.seek(0)
            tempfileIO = StringIO(temp_pdf.read())
            rv = self.app.post('/api/user/{}/patient_report'.format(service_user.id),
                                content_type='multipart/form-data', 
                                data=dict({'file': (tempfileIO, temp_pdf.name)}))
            self.assert200(rv)
        udoc = db.session.query(UserDocument).order_by(UserDocument.id.desc()).first()
        fpath = os.path.join(current_app.root_path,
                            current_app.config.get("FILE_UPLOAD_DIR"),
                            str(udoc.uuid))
        with open(fpath, 'r') as udoc_file:
            self.assertEqual(udoc_file.read(),test_contents)
        os.remove(fpath)
