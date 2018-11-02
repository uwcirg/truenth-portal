from datetime import datetime
from dateutil.relativedelta import relativedelta

import pytest

from portal.database import db
from portal.models.qb_timeline import ordered_qbs, second_null_safe_datetime
from portal.models.questionnaire_bank import visit_name
from portal.views.user import withdraw_consent
from tests import associative_backdate
from tests.test_questionnaire_bank import TestQuestionnaireBank

"""Additional Test cases needed:

For ordered_qbs generator:
 - if RP changes during active w/ submitted, do the get the orig RP on active, then new
 - if submission during RP change, does it work
 - on initial submission - clear results till next qb
 - on completed submission - correct status
 - on partial submission - correct status before and after overdue
 - intervention associated QBs
 
"""


def test_sort():
    yesterday = datetime.utcnow() - relativedelta(days=1)
    items = set([('b', None), ('a', yesterday),  ('c', datetime.utcnow())])
    results = sorted(list(items), key=second_null_safe_datetime, reverse=True)
    # Assert expected order
    x, y = results.pop()
    assert x == 'a'
    x, y = results.pop()
    assert x == 'c'
    x, y = results.pop()
    assert x == 'b'


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
            assert visit_name(next(gen)) == 'Month {}'.format(n)

        with pytest.raises(StopIteration):
            next(gen)

    def test_change_midstream_rp(self):
        now = datetime.utcnow()
        back7, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=7))
        back14, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=14))
        org = self.setup_qbs(rp_name='v2', retired_as_of=back7)
        org_id = org.id
        self.setup_qbs(org=org, rp_name='v3')
        self.consent_with_org(org_id=org_id, setdate=back14)
        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user)

        # expect baseline and 3 month in v2, rest in v3
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        assert (
            expect_baseline.questionnaire_bank.research_protocol.name == 'v2')
        for n in (3, 6):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v2'
        for n in (9, 15, 18, 21, 30):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v3'

        with pytest.raises(StopIteration):
            next(gen)

    def test_change_before_start_rp(self):
        now = datetime.utcnow()
        back7, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=7))
        back14, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=14))
        org = self.setup_qbs(rp_name='v2', retired_as_of=back14)
        org_id = org.id
        self.setup_qbs(org=org, rp_name='v3')
        self.consent_with_org(org_id=org_id, setdate=back7)
        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user)

        # expect everything in v3
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        assert (
            expect_baseline.questionnaire_bank.research_protocol.name == 'v3')
        for n in (3, 6, 9, 15, 18, 21, 30):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v3'

        with pytest.raises(StopIteration):
            next(gen)
