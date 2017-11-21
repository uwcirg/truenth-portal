from tests import TestCase
from flask_webtest import SessionScope

from portal.config.model_persistence import ModelPersistence
from portal.database import db
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
