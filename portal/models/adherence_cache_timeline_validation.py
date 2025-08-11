"""Mechanism to validate Adherence Cache data against QB Timeline"""
from datetime import datetime
import re
from sqlalchemy import and_, delete, text

from portal.database import db
from portal.models.adherence_data import AdherenceData
from portal.models.qb_timeline import visit_name
from portal.models.questionnaire_bank import QBD
from portal.models.reporting import single_patient_adherence_data
from portal.models.research_study import EMPRO_RS_ID
from portal.models.role import ROLE
from portal.models.user import unchecked_get_user
from portal.timeout_lock import ADHERENCE_DATA_KEY, CacheModeration

now = datetime.utcnow()


def baseline_id(study_id):
    baseline_ids = [None, None]

    def lookup():
        nonlocal baseline_ids
        if baseline_ids[study_id] is not None:
            return baseline_ids[study_id]
        baseline_ids[study_id] = []
        query = text("select id from questionnaire_banks where name = :name")
        if study_id == EMPRO_RS_ID:
            baseline_ids[study_id].append(db.engine.execute(query, {"name": "ironman_ss_baseline"}).first()[0])
        else:
            # Due to protocol change, multiple potential baseline IDs
            query = text("select id from questionnaire_banks where name like :name")

            results = []
            for r in db.engine.execute(query, {"name": "IRONMAN_%baseline"}):
                results.append(r[0])

            baseline_ids[study_id] = tuple(results)
        return baseline_ids[study_id]
    return lookup()

def cached_visit_name(qbd):
    cached = {}

    def lookup():
        nonlocal cached
        key = f"{qbd.qb_id}:{qbd.recur_id}:{qbd.iteration}"
        if key in cached:
            return cached[key]
        value = visit_name(qbd)
        cached[key] = value
        return value

    return lookup()



class CombinedData:
    """Special container for comparing a patients adherence vs QB timeline data"""

    def __init__(self, patient_id, study_id):
        self.patient_id = patient_id
        self.study_id = study_id
        self.adherence_data = None
        self.timeline_data = None
        self.report_called = False
        self.withdrawal_month = None

    def adherence_months_by_patient(self):
        this_patient_months = {}
        query = text(
            "select rs_id_visit, data->>'status' as status from adherence_data where patient_id = "
            ":patient_id and rs_id_visit like :rs_pattern")
        for row in db.engine.execute(
                query, {"patient_id": self.patient_id, "rs_pattern": f"{self.study_id}:%"}):
            if row.rs_id_visit.endswith("Indefinite"):
                # Skipping the indefinite check for the time being
                continue
            if row.rs_id_visit.endswith("Baseline"):
                visit_month = 0
            else:
                match = re.findall(r'\d+', row.rs_id_visit)
                if not match:
                    raise ValueError(f"Patient {self.patient_id} has bogus rs_id_visit value: {row.rs_id_visit}")
                visit_month = int(match[-1])

            if row.status == 'Withdrawn':
                self.withdrawal_month = visit_month

            this_patient_months[visit_month] = row.status

        self.adherence_data = this_patient_months

    def timeline_months_by_patient(self):
        patient_timeline_months = {}
        # Use the order built into qb_timeline, with a `due` status starting each visit.
        # build list of (qb_timeline.id, qb_timeline.at) for each respective visit.
        query = text(
            "select id, at, status, qb_id, qb_recur_id, qb_iteration from qb_timeline"
            "  where user_id = :patient_id and"
            "  at < :now and"
            "  research_study_id = :study_id order by id"
        )
        month = 0
        for row in db.engine.execute(
                query, {"patient_id":self.patient_id, "now": now, "study_id":self.study_id}):
            qbd = QBD(relative_start=None, qb_id=row.qb_id, recur_id=row.qb_recur_id, iteration=row.qb_iteration)
            visit = cached_visit_name(qbd)
            match = re.findall(r'\d+', visit)
            if match:
                month = int(match[-1])
            elif not match and visit != 'Baseline':
                raise ValueError(f"Patient {self.patient_id} has bogus rs_id_visit value: {visit}")

            if row.status == 'withdrawn':
                if self.withdrawal_month is not None and self.withdrawal_month != month:
                    raise ValueError(f"mismatch on patient {self.patient_id}, withdrawal months between "
                                     f"adherence {self.withdrawal_month} and timeline {month} disagree")
                self.withdrawal_month = month

                # TN-3349, if the first event in the timeline is withdrawal, the user withdrew
                # before the study started.  there won't be adherence data.  don't collect any
                # additional timeline data as it'll only prove misleading.
                if len(patient_timeline_months) == 0:
                    break

            # update with latest status, as order in db implies what's most current
            patient_timeline_months[month] = {"status": row.status}
        self.timeline_data = patient_timeline_months

    def report(self, message):
        if not self.report_called:
            self.report_called = True
            print(f"Differences for {self.patient_id} adherence | qb_timeline")
        print(message)

    def show_differences(self):
        if not self.adherence_data  and not self.timeline_data:
            return None
        all_timeline_status = {r['status'] for r in self.timeline_data.values()}
        if not self.adherence_data  and all_timeline_status == {'expired'}:
            return None

        retval = None
        # Iterate over all known visit months.
        max = 60
        if self.study_id == EMPRO_RS_ID:
            max = 12
        for i in range(1,max+1):
            ad = self.adherence_data.get(i)
            td = self.timeline_data.get(i)
            if ad is None and td is None:
                continue
            if ad and not td:
                self.report(f"\tmonth {i}:\t {ad} != None")
                retval = True
                continue
            if td and not ad:
                # beyond withdrawal, ignore td only rows
                if self.withdrawal_month is not None and i > self.withdrawal_month:
                    continue
                self.report(f"\tmissing adherence for month {i}")
                retval = True
                continue
            if ad.lower() != td["status"]:
                # account for multi-word status differences
                if ((ad == "Partially Completed" and td["status"] == "partially_completed") or
                        (ad == "In Progress" and td["status"] == "in_progress")):
                        continue

                # at or beyond withdrawal, complex ordering of post-withdrawal and handling
                # to complex for this level check
                if self.withdrawal_month and i >= self.withdrawal_month:
                    continue

                self.report(f"\tmonth {i}:\t {ad} != {td}")
                retval = True
        return retval


def validate(research_study_id, reprocess):
    reprocess_ids = []
    def patient_loop():
        query = text(
            "select distinct(user_id) from qb_timeline where research_study_id = :study_id "
            "order by user_id")

        for row in db.engine.execute(query, {"study_id": research_study_id}):
            pat_id = row.user_id
            patient = unchecked_get_user(pat_id, allow_deleted=True)
            if patient.has_role(ROLE.TEST.value) or patient.deleted_id is not None:
                continue

            pat_diff = CombinedData(pat_id, research_study_id)
            pat_diff.adherence_months_by_patient()
            pat_diff.timeline_months_by_patient()

            if pat_diff.show_differences():
                reprocess_ids.append(pat_id)

    patient_loop()
    if not reprocess:
        return

    for pat_id in reprocess_ids:
        # force a rebuild of adherence data on all patients found to have problems
        print(f"reprocess {pat_id}")
        cache_moderation = CacheModeration(key=ADHERENCE_DATA_KEY.format(
            patient_id=pat_id,
            research_study_id=research_study_id))
        cache_moderation.reset()
        stmt = delete(AdherenceData).where(and_(
            AdherenceData.patient_id == pat_id,
            AdherenceData.rs_id_visit.like(f"%{research_study_id}:%")))
        db.session.execute(stmt)
        db.session.commit()
        single_patient_adherence_data(patient_id=pat_id, research_study_id=research_study_id)
