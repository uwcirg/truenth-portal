"""Unit test module for user document logic"""

from datetime import datetime
from io import BytesIO
import os

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
        response = self.client.get(
            '/api/user/{}/user_documents'.format(TEST_USER_ID))
        assert response.status_code == 200
        assert len(response.json['user_documents']) == 2
        # tests document_type filter
        response = self.client.get(
            '/api/user/{}/user_documents?document_type=TestFile'.format(
                TEST_USER_ID))
        assert response.status_code == 200
        assert len(response.json['user_documents']) == 1
        assert (response.json['user_documents'][0]['uploaded_at']
                == FHIR_datetime.as_fhir(now))

    def test_post_patient_report(self):
        # tests whether we can successfully post a patient report -type
        # user doc file
        client = self.add_client()
        client.intervention = INTERVENTION.SEXUAL_RECOVERY
        create_service_token(client=client, user=get_user(TEST_USER_ID))
        self.login()

        test_contents = b"This is a test."
        response = self.client.post(
            '/api/user/{}/patient_report'.format(TEST_USER_ID),
            content_type='multipart/form-data',
            data={'file': (BytesIO(test_contents), 'udoc_test.pdf')})

        assert response.status_code == 200
        udoc = db.session.query(UserDocument).order_by(
            UserDocument.id.desc()).first()
        fpath = os.path.join(
            current_app.root_path, current_app.config.get("FILE_UPLOAD_DIR"),
            str(udoc.uuid))
        with open(fpath, 'rb') as udoc_file:
            assert udoc_file.read() == test_contents
        os.remove(fpath)

        assert udoc.user_id == TEST_USER_ID
        assert (udoc.intervention.description
                == INTERVENTION.SEXUAL_RECOVERY.description)

    def test_download_user_document(self):
        self.login()
        test_contents = b"This is a test."
        response = self.client.post(
            '/api/user/{}/patient_report'.format(TEST_USER_ID),
            content_type='multipart/form-data',
            data={'file': (BytesIO(test_contents), 'udoc_test.pdf')})
        assert response.status_code == 200

        udoc = db.session.query(UserDocument).order_by(
            UserDocument.id.desc()).first()
        response = self.client.get('/api/user/{}/user_documents/{}'.format(
            TEST_USER_ID, udoc.id))
        assert response.status_code == 200
        assert response.data == test_contents
