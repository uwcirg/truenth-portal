"""Fix obliterated observations

Revision ID: f64288c5fd6f
Revises: a22bf5c68d33
Create Date: 2018-04-18 11:30:12.592050

"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'f64288c5fd6f'
down_revision = 'a22bf5c68d33'


def upgrade():
    """ Fix for issue TN-943, where a second like observation hides the first

    Need to track down any users with multiple values for {biopsy, PCaDIAG,
    PCaLocalized} and preserve the older, IFF the newer is just placeholder
    data.

    The source of this comes from interventions failing to check for existing
    values prior to setting defaults, such as "unknown" to avoid initial
    queries.

    """
    conn = op.get_bind()

    # Grab list of effected users and the respective coding id
    query = """
        SELECT user_id, coding_id
        FROM observations
          JOIN user_observations ON observations.id = user_observations.observation_id
          JOIN codeable_concept_codings ON observations.codeable_concept_id = codeable_concept_codings.codeable_concept_id
          JOIN codings ON codeable_concept_codings.coding_id = codings.id
        WHERE system = 'http://us.truenth.org/clinical-codes'
          AND code in ('111', '121', '141')
        GROUP BY user_id, coding_id HAVING count(coding_id) > 1
    """
    subquery = text("""
        SELECT user_observations.id, user_observations.audit_id, status FROM user_observations
          JOIN audit ON user_observations.audit_id = audit.id
          JOIN observations o ON user_observations.observation_id = o.id
          JOIN value_quantities ON o.value_quantity_id = value_quantities.id
          JOIN user_observations observation ON o.id = observation.observation_id
          JOIN codeable_concept_codings ON o.codeable_concept_id = codeable_concept_codings.codeable_concept_id
        WHERE observation.user_id =:user_id AND coding_id =:coding_id ORDER BY timestamp;        
    """)

    del_audits = []
    del_user_observations = []
    for user_id, coding_id in conn.execute(query).fetchall():

        # The first w/o a status of 'unknown' is a keeper
        have_a_keeper = False
        for user_observation_id, audit_id, status in conn.execute(
                subquery, user_id=user_id, coding_id=coding_id):
            if status is None or status != 'unknown':
                have_a_keeper = True
            elif have_a_keeper:
                del_audits.append(audit_id)
                del_user_observations.append(user_observation_id)

    # wipe out all the bogus `unknown` overwrites
    if del_user_observations:
        print "delete user_obs: {}".format(tuple(del_user_observations))
        del_stmt = text("DELETE FROM user_observations WHERE id IN :id_list")
        conn.execute(del_stmt, id_list=tuple(del_user_observations))

    if del_audits:
        print "delete audits: {}".format(tuple(del_audits))
        del_stmt = text("DELETE FROM audit WHERE id IN :id_list")
        conn.execute(del_stmt, id_list=tuple(del_audits))


def downgrade():
    # no downgrade for this issue
    pass
