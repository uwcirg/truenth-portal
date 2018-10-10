from alembic import op
from sqlalchemy.orm import sessionmaker

from portal.models.codeable_concept import CodeableConcept
from portal.models.coding import Coding

"""empty message

Revision ID: 875b743d457f
Revises: 9e5c1c6c4d64
Create Date: 2017-11-29 15:27:29.489343

"""

# revision identifiers, used by Alembic.
revision = '875b743d457f'
down_revision = '9e5c1c6c4d64'

Session = sessionmaker()


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    defcode = session.query(Coding).filter_by(system="urn:ietf:bcp:47",
                                              display="Default").first()

    if defcode:
        session.execute("UPDATE organizations set default_locale_id = NULL "
                        "WHERE default_locale_id = {}".format(defcode.id))

        for cc_code_id, cc_id in session.execute(
                "SELECT id, codeable_concept_id FROM codeable_concept_codings "
                "WHERE coding_id = {}".format(defcode.id)):

            session.execute("UPDATE users set locale_id = NULL "
                            "WHERE locale_id = {}".format(cc_id))

            session.execute("DELETE from codeable_concept_codings "
                            "WHERE id = {}".format(cc_code_id))

            session.execute("DELETE from codeable_concepts "
                            "WHERE id = {}".format(cc_id))

        session.execute("DELETE from codings "
                        "WHERE id = {}".format(defcode.id))


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    defcode = Coding(system="urn:ietf:bcp:47", display="Default", code="")
    session.add(defcode)
    session.commit()
    defcode = session.merge(defcode)

    defcc = CodeableConcept(text="")
    defcc.codings.append(defcode)
    session.add(defcc)
    session.commit()
