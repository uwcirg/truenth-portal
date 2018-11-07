from datetime import datetime
from dateutil.relativedelta import relativedelta

import pytest

from portal.database import db
from portal.models.qb_timeline import (
    QBT,
    ordered_qbs,
    second_null_safe_datetime,
    update_users_QBT,
)
from portal.models.questionnaire_bank import QuestionnaireBank, visit_name
from portal.views.user import withdraw_consent
from tests import associative_backdate
from tests.test_assessment_status import mock_qr
from tests.test_questionnaire_bank import TestQuestionnaireBank

"""Additional Test cases needed:

For ordered_qbs generator:
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

    def test_zero_input(self):
        # Basic w/o any QNR submission should generate all default QBTs
        crv = self.setup_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user.organizations.append(crv)
        user = db.session.merge(self.test_user)
        update_users_QBT(user)
        # expect (due, overdue, expired) for each QB (8)
        assert QBT.query.filter(QBT._status == 'due').count() == 8
        assert QBT.query.filter(QBT._status == 'overdue').count() == 8
        assert QBT.query.filter(QBT._status == 'expired').count() == 8

    def test_partial_input(self):
        crv = self.setup_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user.organizations.append(crv)

        # submit a mock response for 3 month QB
        # which should result in status change
        qb_name = "CRV_recurring_3mo_period v2"
        threeMo = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()
        mock_qr('epic26_v2', qb=threeMo, iteration=0)

        user = db.session.merge(self.test_user)
        update_users_QBT(user)
        for q in QBT.query.all():
            print q.qb_id, q.qb_iteration, q.at, q.status
        # for the 8 QBs and verify counts
        # given the partial results, we find one in progress and one
        # partially completed, matching expectations
        assert QBT.query.filter(QBT._status == 'due').count() == 8
        # should be one less overdue as it became in_progress
        assert QBT.query.filter(QBT._status == 'overdue').count() == 7
        # should be one less expired as it became partially_completed
        assert QBT.query.filter(QBT._status == 'expired').count() == 7
        assert QBT.query.filter(QBT._status == 'in_progress').one()
        assert QBT.query.filter(
            QBT._status == 'partially_completed').one()

    def test_partial_post_overdue_input(self):
        crv = self.setup_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user.organizations.append(crv)

        # submit a mock response for 3 month QB after overdue
        # before expired
        post_overdue = datetime.now() + relativedelta(months=4, weeks=1)
        qb_name = "CRV_recurring_3mo_period v2"
        threeMo = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()
        mock_qr('epic26_v2', qb=threeMo, iteration=0, timestamp=post_overdue)

        user = db.session.merge(self.test_user)
        update_users_QBT(user)
        for q in QBT.query.all():
            print q.qb_id, q.qb_iteration, q.at, q.status
        # for the 8 QBs and verify counts
        # given the partial results, we find one in progress and one
        # partially completed, matching expectations
        assert QBT.query.filter(QBT._status == 'due').count() == 8
        assert QBT.query.filter(QBT._status == 'overdue').count() == 8
        # should be one less expired as it became partially_completed
        assert QBT.query.filter(QBT._status == 'expired').count() == 7
        assert QBT.query.filter(QBT._status == 'in_progress').one()
        assert QBT.query.filter(
            QBT._status == 'partially_completed').one()

    def test_completed_input(self):
        # Basic w/ one complete QB
        crv = self.setup_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user.organizations.append(crv)

        # submit a mock response for all q's in 3 mo qb
        # which should result in completed status
        qb_name = "CRV_recurring_3mo_period v2"
        threeMo = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()

        for q in threeMo.questionnaires:
            q = db.session.merge(q)
            mock_qr(q.name, qb=threeMo, iteration=0)

        user = db.session.merge(self.test_user)
        update_users_QBT(user)
        # for the 8 QBs and verify counts
        # given the partial results, we find one in progress and one
        # partially completed, matching expectations
        assert QBT.query.filter(QBT._status == 'due').count() == 8
        # should be one less overdue as it became in_progress
        assert QBT.query.filter(QBT._status == 'overdue').count() == 7
        # should be one less expired as it became partially_completed
        assert QBT.query.filter(QBT._status == 'expired').count() == 7
        assert QBT.query.filter(QBT._status == 'in_progress').one()
        assert QBT.query.filter(QBT._status == 'completed').one()

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

    def test_change_midstream_results_rp(self):
        now = datetime.utcnow()
        back7, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=7))
        back14, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=14))
        org = self.setup_qbs(rp_name='v2', retired_as_of=back7)
        org_id = org.id
        self.setup_qbs(org=org, rp_name='v3')
        self.consent_with_org(org_id=org_id, setdate=back14)

        # submit a mock response for 9 month QB on old RP
        # which should result in v2 for up to 9 month and v3 thereafter
        qb_name = "CRV_recurring_3mo_period v2"
        nineMo = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()
        mock_qr('epic_26_v2', qb=nineMo, iteration=1)

        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user)

        # expect baseline and 3 month in v2, rest in v3
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        assert (
            expect_baseline.questionnaire_bank.research_protocol.name == 'v2')
        for n in (3, 6, 9):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v2'
        for n in (15, 18, 21, 30):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v3'

        with pytest.raises(StopIteration):
            next(gen)

    def test_change_before_start_rp_w_result(self):
        now = datetime.utcnow()
        back7, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=7))
        back14, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=14))
        org = self.setup_qbs(rp_name='v2', retired_as_of=back14)
        org_id = org.id
        self.setup_qbs(org=org, rp_name='v3')
        self.consent_with_org(org_id=org_id, setdate=back7)

        # submit a mock response for baseline QB on old RP
        # which should result in v2 for baseline and v3 thereafter
        qb_name = "CRV Baseline v2"
        baseline = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()
        mock_qr('epic_26_v2', qb=baseline, iteration=None)

        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user)

        # expect everything in v3 post baseline
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        assert (
            expect_baseline.questionnaire_bank.research_protocol.name == 'v2')
        for n in (3, 6, 9, 15, 18, 21, 30):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v3'

        with pytest.raises(StopIteration):
            next(gen)
