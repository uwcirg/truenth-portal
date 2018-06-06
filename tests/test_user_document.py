"""Unit test module for user document logic"""
from StringIO import StringIO
from datetime import datetime
import os
from tempfile import NamedTemporaryFile

from flask import current_app
from flask_webtest import SessionScope

from portal.date_tools import FHIR_datetime
from portal.extensions import db
from portal.models.auth import create_service_token
from portal.models.intervention import INTERVENTION
from portal.models.user import get_user
from portal.models.user_document import UserDocument
from tests import TEST_USER_ID, TestCase


class TestUserDocument(TestCase):
    """User Document tests"""

    def test_get_user_documents(self):
        """tests get the list of user documents for a user"""
        now = datetime.utcnow()
        ud1 = UserDocument(
            document_type="TestFile", uploaded_at=now,
            filename="test_file_1.txt", filetype="txt", uuid="012345")
        ud2 = UserDocument(
            document_type="AlternateTestFile", uploaded_at=now,
            filename="test_file_2.txt", filetype="txt", uuid="098765")
        self.test_user.documents.append(ud1)
        self.test_user.documents.append(ud2)
        with SessionScope(db):
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        self.login()
        rv = self.client.get(
            '/api/user/{}/user_documents'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEqual(len(rv.json['user_documents']), 2)
        # tests document_type filter
        rv = self.client.get(
            '/api/user/{}/user_documents?document_type=TestFile'.format(
                TEST_USER_ID))
        self.assert200(rv)
        self.assertEqual(len(rv.json['user_documents']), 1)
        self.assertEqual(
            rv.json['user_documents'][0]['uploaded_at'],
            FHIR_datetime.as_fhir(now))


    def test_post_patient_report(self):
        #tests whether we can successfully post a patient report -type user doc file
        client = self.add_client()
        client.intervention = INTERVENTION.SEXUAL_RECOVERY
        create_service_token(client=client, user=get_user(TEST_USER_ID))
        self.login()

        test_contents = "This is a test."
        with NamedTemporaryFile(
            prefix='udoc_test_',
            suffix='.pdf',
            delete=True,
        ) as temp_pdf:
            temp_pdf.write(test_contents)
            temp_pdf.seek(0)
            tempfileIO = StringIO(temp_pdf.read())
            rv = self.client.post('/api/user/{}/patient_report'.format(TEST_USER_ID),
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

        self.assertEqual(udoc.user_id, TEST_USER_ID)
        self.assertEqual(udoc.intervention.description,
                          INTERVENTION.SEXUAL_RECOVERY.description)


    def test_download_user_document(self):
        self.login()
        test_contents = "This is a test."
        with NamedTemporaryFile(
            prefix='udoc_test_',
            suffix='.pdf',
            delete=True,
        ) as temp_pdf:
            temp_pdf.write(test_contents)
            temp_pdf.seek(0)
            tempfileIO = StringIO(temp_pdf.read())
            rv = self.client.post('/api/user/{}/patient_report'.format(TEST_USER_ID),
                                content_type='multipart/form-data', 
                                data=dict({'file': (tempfileIO, temp_pdf.name)}))
            self.assert200(rv)
        udoc = db.session.query(UserDocument).order_by(UserDocument.id.desc()).first()
        rv = self.client.get('/api/user/{}/user_documents/{}'.format(
                            TEST_USER_ID,udoc.id))
        self.assert200(rv)
        self.assertEqual(rv.data,test_contents)
