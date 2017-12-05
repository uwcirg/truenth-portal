from tests import TestCase
from flask_webtest import SessionScope
from shutil import rmtree
from tempfile import mkdtemp

from portal.config.model_persistence import ModelPersistence
from portal.database import db
from portal.models.app_text import AppText
from portal.models.communication_request import CommunicationRequest
from portal.models.fhir import Coding
from portal.models.organization import Organization
from portal.system_uri import SNOMED


class TestModelPersistence(TestCase):

    def setUp(self):
        super(TestModelPersistence, self).setUp()
        self.tmpdir = mkdtemp()

    def tearDown(self):
        super(TestModelPersistence, self).tearDown()
        rmtree(self.tmpdir)

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

    def test_composite_key(self):
        known_coding =  Coding(
            system=SNOMED, code='26294005',
            display='Radical prostatectomy (nerve-sparing)').add_if_not_found(True)

        mp = ModelPersistence(
            Coding, sequence_name='codings_id_seq', lookup_field=('system', 'code'))
        data = known_coding.as_fhir()

        # Modify only the `display` - composite keys should still match
        modified_data = data.copy()
        modified_data['display'] = 'Radical prostatectomy'
        modified = Coding.from_fhir(data)
        match, _ = mp.lookup_existing(new_obj=modified, new_data=modified_data)
        self.assertEquals(data, match.as_fhir())

        # Import and see the change
        updated = mp.update(modified_data)
        self.assertEquals(modified, updated)

        # Export and verify
        serial = mp.serialize()
        self.assertTrue(modified_data in serial)

    def test_delete_unnamed(self):
        keeper = AppText(name='keep me', custom_text='worthy')
        mp = ModelPersistence(
            AppText, lookup_field='name', sequence_name='apptext_id_seq')
        with SessionScope(db):
            db.session.add(keeper)
            db.session.commit()
        mp.export(target_dir=self.tmpdir)

        # Add another app text, expecting it'll be removed
        bogus = AppText(name='temp', custom_text='not worthy')
        with SessionScope(db):
            db.session.add(bogus)
            db.session.commit()

        # Import w/ keep_unmentioned and expect both
        mp.import_(keep_unmentioned=True, target_dir=self.tmpdir)
        self.assertEquals(AppText.query.count(), 2)

        # Now import, and expect only keeper to remain
        mp.import_(keep_unmentioned=False, target_dir=self.tmpdir)
        self.assertEquals(AppText.query.count(), 1)
        self.assertEquals(AppText.query.first().name, 'keep me')
