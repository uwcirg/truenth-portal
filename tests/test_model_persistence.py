from datetime import datetime
import json
import os
from shutil import rmtree
from tempfile import mkdtemp

from flask_webtest import SessionScope
import pytest
from sqlalchemy.orm.exc import NoResultFound

from portal.config.model_persistence import ModelPersistence
from portal.database import db
from portal.date_tools import FHIR_datetime
from portal.models.app_text import AppText
from portal.models.coding import Coding
from portal.models.communication_request import CommunicationRequest
from portal.models.locale import LocaleConstants
from portal.models.organization import Organization, ResearchProtocolExtension
from portal.models.research_protocol import ResearchProtocol
from portal.models.scheduled_job import ScheduledJob
from portal.system_uri import SNOMED
from tests import TestCase


class TestModelPersistence(TestCase):

    def setUp(self):
        super(TestModelPersistence, self).setUp()
        self.tmpdir = mkdtemp()

    def tearDown(self):
        super(TestModelPersistence, self).tearDown()
        rmtree(self.tmpdir)

    def test_adjust_sequence(self):
        mp = ModelPersistence(
            Organization, sequence_name='organizations_id_seq')
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
        nextval = db.engine.execute(
            "SELECT NEXTVAL('{}')".format(
                'organizations_id_seq')).fetchone()[0]
        assert currval == id
        assert nextval > id

    def test_identifier_lookup(self):
        # setup a minimal communication request
        from tests.test_communication import mock_communication_request
        from tests.test_assessment_status import mock_tnth_questionnairebanks
        from portal.system_uri import TRUENTH_CR_NAME
        from portal.models.identifier import Identifier
        mock_tnth_questionnairebanks()
        cr = mock_communication_request(
            'symptom_tracker_recurring', '{"days": 14}')
        cr.identifiers.append(
            Identifier(value='2 week ST', system=TRUENTH_CR_NAME))
        with SessionScope(db):
            db.session.add(cr)
            db.session.commit()
        cr = db.session.merge(cr)
        assert cr.identifiers.count() == 1

        data = cr.as_fhir()
        mp = ModelPersistence(
            CommunicationRequest,
            sequence_name='communication_requests_id_seq',
            lookup_field='identifier')
        new_obj = CommunicationRequest.from_fhir(data)
        match, field_description = mp.lookup_existing(
            new_obj=new_obj, new_data=data)
        assert match.name == cr.name

    def test_composite_key(self):
        known_coding = Coding(
            system=SNOMED, code='26294005',
            display='Radical prostatectomy (nerve-sparing)').add_if_not_found(
            True)

        mp = ModelPersistence(
            Coding, sequence_name='codings_id_seq',
            lookup_field=('system', 'code'))
        data = known_coding.as_fhir()

        # Modify only the `display` - composite keys should still match
        modified_data = data.copy()
        modified_data['display'] = 'Radical prostatectomy'
        modified = Coding.from_fhir(data)
        match, _ = mp.lookup_existing(
            new_obj=modified, new_data=modified_data)
        assert data == match.as_fhir()

        # Import and see the change
        updated = mp.update(modified_data)
        assert modified == updated

        # Export and verify
        serial = mp.serialize()
        assert modified_data in serial

    def test_delete_unnamed(self):
        keeper = AppText(name='keep me', custom_text='worthy')
        mp = ModelPersistence(
            AppText, lookup_field='name', sequence_name='apptext_id_seq',
            target_dir=self.tmpdir)
        with SessionScope(db):
            db.session.add(keeper)
            db.session.commit()
        mp.export()

        # Add another app text, expecting it'll be removed
        bogus = AppText(name='temp', custom_text='not worthy')
        with SessionScope(db):
            db.session.add(bogus)
            db.session.commit()

        # Import w/ keep_unmentioned and expect both
        mp.import_(keep_unmentioned=True)
        assert AppText.query.count() == 2

        # Now import, and expect only keeper to remain
        mp.import_(keep_unmentioned=False)
        assert AppText.query.count() == 1
        assert AppText.query.first().name == 'keep me'

    def test_delete_extension(self):
        org = Organization(name='testy')
        org.timezone = 'Asia/Tokyo'  # stored in an extension
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        mp = ModelPersistence(
            Organization, lookup_field='id',
            sequence_name='organizations_id_seq',
            target_dir=self.tmpdir)
        mp.export()

        # Strip the empty extensions, as expected in the real persistence file
        with open(
                os.path.join(self.tmpdir, 'Organization.json'), 'r') as pfile:
            data = json.load(pfile)
            # Special handling of extensions - empties only have 'url' key

        for i, entry in enumerate(data['entry']):
            extensions = entry['extension']
            keepers = []
            for e in extensions:
                if len(e.keys()) > 1:
                    keepers.append(e)
            data['entry'][i]['extension'] = keepers
            empty_keys = [k for k, v in entry.items() if not v]
            for k in empty_keys:
                del data['entry'][i][k]

        with open(
                os.path.join(self.tmpdir, 'Organization.json'), 'w') as pfile:
            pfile.write(json.dumps(data))

        # Add an additional extension to the org, make sure
        # they are deleted when importing again from
        # persistence that doesn't include them

        org.locales.append(LocaleConstants().AmericanEnglish)
        with SessionScope(db):
            db.session.commit()
        org = db.session.merge(org)
        assert len(org.as_fhir()['extension']) > 1

        mp.import_(keep_unmentioned=False)
        org = Organization.query.filter(Organization.name == 'testy').one()
        assert org.locales.count() == 0
        assert org.timezone == 'Asia/Tokyo'

    def test_delete_identifier(self):
        # orgs losing identifiers should delete the orphans
        from portal.system_uri import SHORTCUT_ALIAS, TRUENTH_CR_NAME
        from portal.models.identifier import Identifier

        org = Organization(name='testy')
        org.identifiers.append(Identifier(
            value='2 week ST', system=TRUENTH_CR_NAME))
        org.identifiers.append(Identifier(
            value='ohsu', system=SHORTCUT_ALIAS))
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        mp = ModelPersistence(
            Organization, lookup_field='id',
            sequence_name='organizations_id_seq',
            target_dir=self.tmpdir)
        mp.export()

        # Reduce identifiers to one - make sure the other identifier goes away
        with open(
                os.path.join(self.tmpdir, 'Organization.json'), 'r') as pfile:
            data = json.load(pfile)

        for i, entry in enumerate(data['entry']):
            identifiers = entry['identifier']
            keepers = [
                identifier for identifier in identifiers
                if identifier['system'] == SHORTCUT_ALIAS]
            data['entry'][i]['identifier'] = keepers

        with open(
                os.path.join(self.tmpdir, 'Organization.json'), 'w') as pfile:
            pfile.write(json.dumps(data))

        mp.import_(keep_unmentioned=False)
        org = Organization.query.filter(Organization.name == 'testy').one()
        assert org.identifiers.count() == 1

        # Make sure we cleared out the orphan
        with pytest.raises(NoResultFound):
            Identifier.query.filter_by(
                value='2 week ST', system=TRUENTH_CR_NAME).one()

    def test_missing_scheduled_job(self):
        # unmentioned scheduled job should get deleted
        schedule = "45 * * * *"
        sj = ScheduledJob(
            name="test_sched", task="test", schedule=schedule, active=True)
        sj2 = ScheduledJob(
            name="test_sched2", task="test", schedule=schedule, active=True)
        with SessionScope(db):
            db.session.add(sj)
            db.session.add(sj2)
            db.session.commit()
        assert ScheduledJob.query.count() == 2

        mp = ModelPersistence(
            ScheduledJob, lookup_field='name',
            sequence_name='scheduled_jobs_id_seq',
            target_dir=self.tmpdir)
        mp.export()

        # Reduce identifiers to one - make sure the other identifier goes away
        with open(
                os.path.join(self.tmpdir, 'ScheduledJob.json'), 'r') as pfile:
            data = json.load(pfile)

        # chop the first
        data['entry'] = data['entry'][1:]

        with open(
                os.path.join(self.tmpdir, 'ScheduledJob.json'), 'w') as pfile:
            pfile.write(json.dumps(data))

        mp.import_(keep_unmentioned=False)
        assert ScheduledJob.query.count() == 1

    def test_rp_alteration(self):
        # orgs with old rp should migrate to multiple w/ updated retired
        from portal.system_uri import SHORTCUT_ALIAS, TRUENTH_CR_NAME
        from portal.models.identifier import Identifier

        rp1 = ResearchProtocol(name='initial', research_study_id=0)
        rp2 = ResearchProtocol(name='replacement', research_study_id=0)
        org = Organization(name='testy')
        org.research_protocols.append(rp1)
        with SessionScope(db):
            db.session.add(rp2)
            db.session.add(org)
            db.session.commit()
        mp = ModelPersistence(
            Organization, lookup_field='id',
            sequence_name='organizations_id_seq',
            target_dir=self.tmpdir)
        mp.export()

        # Add second rp, mark old as retired
        with open(
                os.path.join(self.tmpdir, 'Organization.json'), 'r') as pfile:
            data = json.load(pfile)

        now = datetime.utcnow().replace(microsecond=0)
        updated = {
            'url': ResearchProtocolExtension.extension_url,
            'research_protocols': [
                {"name": 'replacement'},
                {"name": 'initial', "retired_as_of": FHIR_datetime.as_fhir(
                    now)}]}
        for i, entry in enumerate(data['entry']):
            if entry['name'] != 'testy':
                continue
            extensions = entry['extension']
            keepers = [
                ext for ext in extensions
                if ext['url'] != ResearchProtocolExtension.extension_url]
            keepers.append(updated)
            data['entry'][i]['extension'] = keepers

        with open(
                os.path.join(self.tmpdir, 'Organization.json'), 'w') as pfile:
            pfile.write(json.dumps(data))

        mp.import_(keep_unmentioned=False)
        org = Organization.query.filter(Organization.name == 'testy').one()
        assert len(org.research_protocols) == 2

        # Make sure retired_as_of was set properly on old
        rp1, rp2 = map(db.session.merge, (rp1, rp2))
        expected = [(rp2, None), (rp1, now)]
        results = [
            (rp, retired) for rp, retired in
            org.rps_w_retired(research_study_id=0)]
        assert results == expected
