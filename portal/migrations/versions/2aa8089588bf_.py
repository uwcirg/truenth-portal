"""Correct trigger_states visit month

Revision ID: 2aa8089588bf
Revises: f9701b16fccb
Create Date: 2022-11-03 14:34:30.640152

"""
from alembic import op
from collections import OrderedDict, defaultdict
from datetime import timedelta
from sqlalchemy.orm import sessionmaker

from portal.audit import Audit
from portal.models.user import User, unchecked_get_user
from portal.models.user_consent import consent_withdrawal_dates
from portal.models.qb_timeline import update_users_QBT
from portal.models.questionnaire_response import QuestionnaireResponse
from portal.models.research_study import EMPRO_RS_ID
from portal.trigger_states.empro_states import lookup_visit_month

# revision identifiers, used by Alembic.
revision = '2aa8089588bf'
down_revision = 'f9701b16fccb'

Session = sessionmaker()


def purge_timeline(patient_id):
    sys_user = User.query.filter_by(email='__system__').one()

    QuestionnaireResponse.purge_qb_relationship(
        subject_id=patient_id,
        research_study_id=EMPRO_RS_ID,
        acting_user_id=sys_user.id)

    update_users_QBT(
        patient_id,
        research_study_id=EMPRO_RS_ID,
        invalidate_existing=True)


def correct_visit(session, patient_id, visit_month):
    """Correct visit_month for respective trigger_states rows"""
    ts_results = {r.id: (r.state, r.timestamp) for r in session.execute(
        f"SELECT id, state, timestamp FROM trigger_states "
        f"WHERE visit_month = {visit_month} "
        f"AND user_id = {patient_id} ORDER BY id")}

    # sometimes the timestamp from the due was left behind from a previous
    # visit use the in-process row time to lookup the correct visit
    try:
        best_row = [
            r[1] for r in ts_results.values() if r[0] == 'inprocess']
        if not best_row:
            # none found for the desired visit 'inprocess';
            # happens on a new visit with only the due state
            assert len(ts_results) == 1
            best_row = [r[1] for r in ts_results.values() if r[0] == 'due']

        lookuptime = best_row[0]
        desired_month = lookup_visit_month(patient_id, lookuptime)
    except IndexError as e:
        print(
            f"failure to locate reference date, {patient_id} probably"
            f" needs a timeline purge")
        raise e

    for row_id in ts_results.keys():
        # shift the `due` to moments before user initiated work, in case it's on
        # the wrong visit
        if ts_results[row_id][0] == 'due':
            ts = lookuptime - timedelta(seconds=5)
            stmt = (
                f"UPDATE trigger_states SET timestamp = '{ts}', "
                f"visit_month = {desired_month} WHERE id = {row_id}")
        else:
            stmt = (
                f"UPDATE trigger_states SET visit_month = {desired_month} WHERE id = {row_id}"
            )

        if True:
            message = (
                f"migration updating trigger_states({row_id}): "
                f"from state {ts_results[row_id][0]}, "
                f"timestamp {ts_results[row_id][1]}, "
                f"visit_month {visit_month}")
            aud = Audit(
                comment=message,
                user_id=patient_id,
                subject_id=patient_id,
                _context="assessment")
            session.add(aud)
        session.execute(stmt)


def capture_state(session, patient_id):
    """Generate print friendly details for visual comparison"""
    ts_results = [
        ("{:<3}".format(str(r.id)), "{:<10}".format(r.state),
         r.timestamp.strftime("%Y-%m-%d"), str(r.visit_month))
        for r in session.execute(
            f"SELECT id, state, timestamp, visit_month FROM trigger_states "
            f"WHERE user_id = {patient_id} ORDER BY id")]
    return ts_results


def upgrade():
    """Fix trigger_states rows needing attention

    The visit_month in trigger_states was only getting incremented when
    users submitted work.  Therefore, any patients that skipped a visit
    and then resumed EMPRO work, have the wrong visit_month in some
    trigger_states rows.  This migration corrects the problem.
    """

    bind = op.get_bind()
    session = Session(bind=bind)

    patient_ids = []
    for patient_id in session.execute(
            "SELECT DISTINCT(user_id) FROM trigger_states JOIN users"
            " ON users.id = user_id WHERE deleted_id IS NULL"):
        patient_ids.append(patient_id[0])

    corrections_needed = []
    due_dates = {}
    for patient_id in patient_ids:
        # The following hardcoded user.ids require special handling. They
        # lost a "completed" global status effecting their EMPRO trigger date,
        # due to another issue.  See TN-3202 for details
        if patient_id in (2904, 3015):
            continue

        # Force a timeline clean up - found several out of sync, esp withdrawn
        purge_timeline(patient_id)

        _, withdrawal_date = consent_withdrawal_dates(
            unchecked_get_user(patient_id), EMPRO_RS_ID)

        ts_results = session.execute(
            f"SELECT id, timestamp, state, visit_month FROM trigger_states "
            f"WHERE user_id = {patient_id} ORDER BY id")

        # Group ts_results by recorded visit.  Necessary to break as
        # due and in-process often refer to different visit_months, but
        # need to be migrated and corrected together
        visits = defaultdict(list)
        for row in ts_results:
            visits[row.visit_month].append(row)
        # convert to ordered as required to process in order or clobber
        ts_by_visit = OrderedDict(visits)

        # qb_iteration starts at zero, baseline is the real "first" month
        start_dates = {r["qb_iteration"]: r["at"] for r in session.execute(
            "SELECT at, qb_iteration FROM qb_timeline "
            "WHERE research_study_id = 1 AND status = 'due' "
            f"AND qb_iteration IS NOT NULL AND user_id = {patient_id}")}
        # add baseline
        baseline = session.execute(
            "SELECT at FROM qb_timeline WHERE research_study_id = 1 AND "
            "status = 'due' AND qb_iteration IS NULL "
            f"AND user_id = {patient_id}").first()
        if not baseline:
            # Test users without a clinician don't have a timeline
            patient = unchecked_get_user(patient_id)
            if next(patient.clinicians, None):
                raise RuntimeError(f"{patient_id} doesn't have a baseline due date?")
            continue
        start_dates[-1] = baseline[0]

        for visit_month, rows in ts_by_visit.items():
            for row in rows:
                best_timestamp = row.timestamp

            # Confirm no gaps or add to list needing migration
            # trigger_states.visit_month = 0 is Baseline
            #   qb_iteration + 1 == trigger_states.visit_month
            start = start_dates.get(visit_month - 1)
            if not start:
                # withdrawn users with backdated withdrawal dates sometimes
                # include submitted results after the backdated withdrawal date.
                # ignore if withdrawn and one beyond expected.
                if withdrawal_date and len(start_dates) + 1 == visit_month:
                    print(f"SKIPPING {patient_id} {visit_month}")
                    continue

            next_start = start_dates.get(visit_month)
            if not next_start:
                # happens at end on withdrawn users, add 1 month to start
                if not start:
                    # extreme case added another due after withdrawal during
                    # previous month
                    start = start_dates.get(
                        visit_month - 2) + timedelta(days=31)

                next_start = start + timedelta(days=31)

            if start < best_timestamp < next_start:
                # No correction needed
                continue

            # print(f"needs correction {patient_id}: visit {ts.visit_month}")
            corrections_needed.append((patient_id, visit_month))

            # Retain for reporting changes
            due_dates[patient_id] = OrderedDict(sorted(start_dates.items()))
            if withdrawal_date:
                due_dates[patient_id]["Withdrawn"] = (
                    withdrawal_date.strftime("%Y-%m-%d"))

    distinct_patients = {patient_id for patient_id, visit_month in corrections_needed}
    before_state = {
        patient_id: capture_state(session, patient_id)
        for patient_id in distinct_patients}
    # work backwards to avoid overwriting the corrected visit month
    corrections_needed.reverse()
    for patient_id, visit_month in corrections_needed:
        correct_visit(session, patient_id, visit_month)

    session.commit()
    after_state = {
        patient_id: capture_state(session, patient_id)
        for patient_id in distinct_patients}

    # present side by side results for easy visual
    for id in sorted(distinct_patients):
        print(f"\n\nPatient {id}\n  Actual Due dates for each visit_month:")
        for k, v in due_dates[id].items():
            if k == 'Withdrawn':
                print(f"    {v} {k}")
            else:
                print(f"    {v}    {k+1}")
        print(f"\n  Changes made to patient {id}:")
        print("{:<29}before | after".format(" "))
        print("    id state  timestamp visit_month |    id state  timestamp  visit_month")
        for b, a in zip(before_state[id], after_state[id]):
            print(f"    {' '.join(b):<32}|    {' '.join(a)}")


def downgrade():
    """nop downgrade: of no value, to recreate"""
    pass
