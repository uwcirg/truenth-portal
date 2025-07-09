"""Mechanism to validate the adherence cache matches the trigger state tables"""
from datetime import datetime, timedelta
import re
from sqlalchemy import text

from portal.database import db
from portal.models.adherence_data import AdherenceData
from portal.models.reporting import single_patient_adherence_data
from portal.models.research_study import EMPRO_RS_ID
from portal.models.role import ROLE
from portal.models.user import unchecked_get_user
from portal.models.user_consent import consent_withdrawal_dates
from portal.timeout_lock import ADHERENCE_DATA_KEY, CacheModeration


state_map = {
    "inprocess": "inprocess",
    "triggered": "triggered",
    "resolved": "Completed",
    "due": "Expired",
}


def baseline_id():
    baseline_ss_id = None

    def lookup():
        nonlocal baseline_ss_id
        if baseline_ss_id is not None:
            return baseline_ss_id
        query = text("select id from questionnaire_banks where name = :name")
        baseline_ss_id = db.engine.execute(query, {"name": "ironman_ss_baseline"}).first()[0]
        return baseline_ss_id
    return lookup()


class CombinedData:
    """Special container for comparing a patients adherence vs trigger states data"""

    def __init__(self, patient_id):
        self.patient_id = patient_id
        self.adherence_data = None
        self.ts_data = None
        self.report_called = False
        self.withdrawal_month = None

    def adherence_months_by_patient(self):
        this_patient_months = {}
        query = text(
            "select rs_id_visit, data->>'status' as status from adherence_data where patient_id = "
            ":patient_id and rs_id_visit like :rs1_pattern")
        for row in db.engine.execute(query, {"patient_id": self.patient_id, "rs1_pattern": "1:Month%"}):
            match = re.findall(r'\d+', row.rs_id_visit)
            if not match:
                raise ValueError(f"Patient {self.patient_id} has bogus rs_id_visit value: {r2.rs_id_visit}")
            this_patient_months[int(match[-1])] = row.status
            if row.status == 'Withdrawn':
                self.withdrawal_month = int(match[-1])

        self.adherence_data = this_patient_months
        if self.withdrawal_month:
            return

        # if withdrawal_month wasn't found, calculate now if user has withdrawn
        patient = unchecked_get_user(self.patient_id, allow_deleted=True)
        _, withdrawal = consent_withdrawal_dates(patient, EMPRO_RS_ID)
        if not withdrawal:
            return
        query = text(
            "select at from qb_timeline where qb_id = :baseline and status = 'due' "
            "and research_study_id = 1 and user_id = :user_id")
        result = db.engine.execute(query, {"baseline": baseline_id(), "user_id": self.patient_id}).first()[0]
        withdrawal_month = -1
        while True:
            if withdrawal < result:
                self.withdrawal_month = withdrawal_month
                return
            result += timedelta(days=30)
            withdrawal_month += 1
            assert withdrawal_month < 12

    def trigger_states_months_by_patient(self):
        this_patient_ts_months = {}
        query = text(
            "select visit_month, state from trigger_states where user_id = :patient_id order by id"
        )
        for row in db.engine.execute(query, {"patient_id":self.patient_id}):
            # allow to overwrite improved state given order
            visit_month = row.visit_month + 1  # 0 index, align with adherence
            this_patient_ts_months[visit_month] = state_map[row.state]
        self.ts_data = this_patient_ts_months

    def report(self, message):
        if not self.report_called:
            self.report_called = True
            print(f"Differences for {self.patient_id} adherence | trigger states")
        print(message)

    def show_differences(self):
        if self.adherence_data is None and self.ts_data is None:
            return None
        for i in range(1,13):
            ad = self.adherence_data.get(i)
            ts = self.ts_data.get(i)
            if ad is None and ts is None:
                continue
            if ad and not ts:
                if ad in ('Due', 'Expired', 'Overdue', 'Not Yet Available'):
                    # trigger states often never started w/o user intervention
                    continue
                if ad == 'Withdrawn':
                    # trigger states often not generated after withdrawal
                    continue
                if self.patient_id == 5903:
                    # one of a kind, missing trigger_states rows for visit 11
                    # back story: https://cirg.slack.com/archives/C5MH9NVKQ/p1725553251960589?thread_ts=1725553232.355499&cid=C5MH9NVKQ
                    assert i == 11  # the known missing month
                    continue
            if ts and not ad:
                # beyond withdrawal, ignore ts only rows
                if self.withdrawal_month and i > self.withdrawal_month:
                    continue
                self.report(f"\tmissing adherence for month {i}")
            if ad != ts:
                note = ""
                # at or beyond withdrawal, ts of expired is equivalent
                if self.withdrawal_month and i >= self.withdrawal_month and ts == 'Expired':
                    continue
                if ad == 'Completed' and ts == 'triggered':
                    note = "(Matching state pending clinician follow-up)"
                if (
                        ad in ('Due', 'Overdue', 'Not Yet Available') and
                        ts == 'Expired' and
                        i == max(self.ts_data.keys()) and
                        not self.withdrawal_month):
                    # legit mis-mapping from state_map where both are "due"
                    # the not-yet-avail state implies base study must first be completed
                    continue
                self.report(f"\tmonth {i}:\t {ad} != {ts} {note}")


def validate(reprocess):
    reprocess_ids = []
    def patient_loop():
        query = "select distinct(user_id) from trigger_states order by user_id"
        for row in db.engine.execute(query):
            pat_id = row.user_id
            patient = unchecked_get_user(pat_id, allow_deleted=True)
            if patient.has_role(ROLE.TEST.value):
                continue
            pat_diff = CombinedData(pat_id)
            pat_diff.adherence_months_by_patient()
            pat_diff.trigger_states_months_by_patient()

            if pat_diff.show_differences():
                reprocess_ids.append(pat_id)

    patient_loop()
    now = datetime.utcnow()
    if not reprocess:
        return

    for pat_id in reprocess_ids[0:0]:
        # force a rebuild of adherence data on all patients found to have problems
        cache_moderation = CacheModeration(key=ADHERENCE_DATA_KEY.format(
            patient_id=pat_id,
            research_study_id=EMPRO_RS_ID))
        cache_moderation.reset()
        valid = (now + timedelta(hours=1))
        AdherenceData.query.filter(AdherenceData.valid_till < valid).delete()
        db.session.commit()
        single_patient_adherence_data(patient_id=pat_id, research_study_id=EMPRO_RS_ID)
