from tests import TestCase
from flask_webtest import SessionScope

from portal.config.model_persistence import ModelPersistence
from portal.database import db
from portal.models.communication_request import CommunicationRequest
from portal.models.organization import Organization


class TestModelPersistence(TestCase):

    def test_adjust_sequence(self):
        mp = ModelPersistence(Organization, sequence_name='organizations_id_seq')
        # Insert dummy row w/ large id, confirm
        # the sequence becomes greater
        id = 10000
        dummy = Organization(id=id, name='big id')

        with SessionScope(db):
            db.session.add(dummy)
            db.session.commit()

        mp.update_sequence()
        currval = db.engine.execute(
            "SELECT CURRVAL('{}')".format(
                'organizations_id_seq')).fetchone()[0]
        self.assertTrue(currval > id)

    def test_identifier_lookup(self):
        # setup a minimal communication request
        from tests.test_communication import mock_communication_request
        from tests.test_assessment_status import mock_tnth_questionnairebanks
        from portal.system_uri import TRUENTH_CR_NAME
        from portal.models.identifier import Identifier
        mock_tnth_questionnairebanks()
        cr = mock_communication_request('symptom_tracker_recurring', '{"days": 14}')
        cr.identifiers.append(Identifier(value='2 week ST', system=TRUENTH_CR_NAME))
        with SessionScope(db):
            db.session.add(cr)
            db.session.commit()
        cr = db.session.merge(cr)
        self.assertEquals(cr.identifiers.count(), 1)

        data = cr.as_fhir()
        mp = ModelPersistence(
            CommunicationRequest, sequence_name='communication_requests_id_seq',
            lookup_field='identifier')
        new_obj = CommunicationRequest.from_fhir(data)
        match, field_description = mp.lookup_existing(new_obj=new_obj, new_data=data)
        self.assertEquals(match.name, cr.name)
