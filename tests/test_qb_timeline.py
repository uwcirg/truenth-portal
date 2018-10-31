from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytest

from portal.database import db
from portal.models.qb_timeline import ordered_qbs
from portal.models.questionnaire_bank import visit_name
from portal.views.user import withdraw_consent
from tests.test_questionnaire_bank import TestQuestionnaireBank

"""Additional Test cases needed:

For ordered_qbs generator:
 - if RP changes since initial consent, do they get the original RP until change
 - if RP changes during active w/ submitted, do the get the orig RP on active, then new
 - if submission during RP change, does it work
 - on initial submission - clear results till next qb
 - on completed submission - correct status

"""


class TestQbTimeline(TestQuestionnaireBank):

    def test_empty(self):
        # Basic case, without org, empty list
        self.setup_qbs()
        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user=user)
        with pytest.raises(StopIteration):
            next(gen)

    def test_full_list(self):
        crv = self.setup_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user.organizations.append(crv)
        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user=user)

        # expect each in order despite overlapping nature
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        for n in (3, 6, 9, 15, 18, 21, 30):
            assert visit_name(next(gen)) == 'Month {}'.format(n)

        with pytest.raises(StopIteration):
            next(gen)

    def test_withdrawn(self):
        # qbs should halt beyond withdrawal
        crv = self.setup_qbs()
        crv_id = crv.id
        # consent 17 months in past
        backdate = datetime.utcnow() - relativedelta(months=17)
        self.test_user.organizations.append(crv)
        self.consent_with_org(org_id=crv_id, setdate=backdate)

        # withdraw user now, which should provide result
        # in QBs prior to 17 months.

        user = db.session.merge(self.test_user)
        withdraw_consent(user=user, org_id=crv_id, acting_user=user)
        gen = ordered_qbs(user=user)

        # expect each in order despite overlapping nature
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        for n in (3, 6, 9, 15):
            obj=next(gen)
            assert visit_name(obj) == 'Month {}'.format(n)

        with pytest.raises(StopIteration):
            next(gen)
