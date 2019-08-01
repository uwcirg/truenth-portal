
from flask_webtest import SessionScope
import pytest
from werkzeug.exceptions import BadRequest

from portal.database import db
from portal.models.intervention import Intervention
from portal.models.next_step import NextStep
from tests import TestCase


def test_validate():
    assert NextStep.validate('decision_support')


def test_invalid():
    with pytest.raises(BadRequest):
        NextStep.validate('bogus')


class TestNextStep(TestCase):

    def test_decision_support(self):
        # w/o strategy setup, will get back indeterminate ds match
        test_link = 'http://test.me'
        ds_p3p = Intervention.query.filter_by(
            name='decision_support_p3p').one()
        ds_wc = Intervention.query.filter_by(
            name='decision_support_wisercare').one()
        for ds in ds_p3p, ds_wc:
            ds.link_url = test_link
        with SessionScope(db):
            db.session.commit()

        assert test_link == NextStep.decision_support(self.test_user)
