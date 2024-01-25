"""Add sequential hard trigger count to EMPRO trigger_states.triggers domains.

Revision ID: 80c3b1e96c45
Revises: 2e9b9e696bb8
Create Date: 2023-07-24 17:08:35.128975

"""
from collections import defaultdict
from copy import deepcopy
from alembic import op
from io import StringIO
from sqlalchemy.orm import sessionmaker
from portal.database import db
from portal.trigger_states.empro_domains import (
    EMPRO_DOMAINS,
    sequential_hard_trigger_count_key,
)
from portal.trigger_states.models import TriggerState

# revision identifiers, used by Alembic.
revision = '80c3b1e96c45'
down_revision = '66368e673005'

Session = sessionmaker()


def upgrade():
    # Add sequential counts to appropriate trigger_states rows.

    # this migration was applied once before, but the code wasn't correctly
    # maintaining the sequential counts.  start by removing all for a clean
    # slate via the same `downgrade()` step
    downgrade()

    # for each active EMPRO patient with at least 1 hard triggered domain,
    # walk through their monthly reports, adding the sequential count for
    # the opt-out feature.
    bind = op.get_bind()
    session = Session(bind=bind)

    patient_ids = []
    for patient_id in session.execute(
            "SELECT DISTINCT(user_id) FROM trigger_states JOIN users"
            " ON users.id = user_id WHERE deleted_id IS NULL"):
        patient_ids.append(patient_id[0])

    output = StringIO()
    for pid in patient_ids:
        # can't just send through current process, as it'll attempt to
        # insert undesired rows in the trigger_states table.  need to
        # add the sequential count to existing rows.
        output.write(f"\n\nPatient: {pid}  storing all zeros for sequential hard triggers except:\n")
        output.write("  (visit month : domain : # hard sequential)\n")
        sequential_by_domain = defaultdict(list)
        trigger_states = db.session.query(TriggerState).filter(
            TriggerState.user_id == pid).filter(
            TriggerState.state == "resolved").order_by(
            TriggerState.timestamp.asc())
        for ts in trigger_states:
            improved_triggers = deepcopy(ts.triggers)
            for d in EMPRO_DOMAINS:
                sequential_hard_for_this_domain = 0
                if d not in improved_triggers["domain"]:
                    # only seen on test, fill in the missing domain
                    print(f"missing {d} in {pid}:{ts.visit_month}?")
                    improved_triggers["domain"][d] = {}

                if any(v == "hard" for v in improved_triggers["domain"][d].values()):
                    sequential_by_domain[d].append(ts.visit_month)
                    for i in range(ts.visit_month, -1, -1):
                        if i not in sequential_by_domain[d]:
                            break  # any break in sequential months, we start over
                        sequential_hard_for_this_domain += 1
                improved_triggers["domain"][d][
                    sequential_hard_trigger_count_key] = sequential_hard_for_this_domain
                if sequential_hard_for_this_domain > 0:
                    output.write(f"  {ts.visit_month}:{d}: {improved_triggers['domain'][d][sequential_hard_trigger_count_key]}\n")

            # retain triggers now containing sequential counts
            ts.triggers = improved_triggers

        output.write(f" patient's list, by domain, of visit months w/ hard triggers:\n  ")
        for k, v in sequential_by_domain.items():
            output.write(f"{k}: {v}; ")

        db.session.commit()
        print(output.getvalue())


def downgrade():
    # for each active EMPRO patient with at least 1 hard triggered domain,
    # remove any sequential counts found
    bind = op.get_bind()
    session = Session(bind=bind)

    patient_ids = []
    for patient_id in session.execute(
            "SELECT DISTINCT(user_id) FROM trigger_states JOIN users"
            " ON users.id = user_id WHERE deleted_id IS NULL"):
        patient_ids.append(patient_id[0])

    output = StringIO()
    for pid in patient_ids:
        output.write(f"\n\nPatient: {pid}\n")
        trigger_states = db.session.query(TriggerState).filter(
            TriggerState.user_id == pid).filter(
            TriggerState.state == "resolved").order_by(
            TriggerState.timestamp.asc())
        for ts in trigger_states:
            improved_triggers = deepcopy(ts.triggers)
            for d in EMPRO_DOMAINS:
                if d not in improved_triggers["domain"]:
                    raise RuntimeError(f"{d} missing from {ts.visit_month} for {pid}")
                if sequential_hard_trigger_count_key in improved_triggers["domain"][d]:
                    del improved_triggers["domain"][d][sequential_hard_trigger_count_key]
                    output.write(f"  removed sequential from {ts.visit_month}:{d} {improved_triggers['domain'][d]}\n")

            # retain triggers now containing sequential counts
            ts.triggers = improved_triggers

        db.session.commit()
        print(output.getvalue())
