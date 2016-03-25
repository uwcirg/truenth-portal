"""Role module

Role data lives in the `roles` table, populated via:
    `python manage.py seed`

To restrict access to a given role, use the ROLE object:
    @roles_required(ROLE.ADMIN)

To extend the list of roles, add name: description pairs to the
STATIC_ROLES dict within.

"""
from ..extensions import db
from UserDict import IterableUserDict


class Role(db.Model):
    """SQLAlchemy class for `roles` table"""
    __tablename__ = 'roles'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(50), unique=True)
    description = db.Column(db.Text)


#Source definition for roles, as dictionary {name: description,}
STATIC_ROLES = IterableUserDict({
    'admin':
        'Administrator privledges, i.e. carte blanche',
    'anon':
        'Anonymous role - exclusive to accounts generated prior to '
        'user authentication',
    'application_developer':
        'Gives users permission to add/view/edit TrueNTH applications',
    'content_manager':
        'Gives user permission to add/view/edit associated content '
        'managment systems',
    'partner':
        "An intimate partner, use the partner relationship to define "
        "whom the patient's partner is",
    'patient':
        'Default role for all patients, may only view their own '
        'patient data',
    'service':
        'Reserved for automated service accounts needing API access'
        })


def enum(**items):
    """Convert dictionary to Enumeration for direct access"""
    return type('Enum', (), items)

ROLE = enum(**{unicode(r).upper():r for r in STATIC_ROLES})


def add_static_roles():
    """Seed database with default static roles

    Idempotent - run anytime to pick up any new roles in existing dbs

    """
    for r in STATIC_ROLES:
        if not Role.query.filter_by(name=r).first():
            db.session.add(Role(name=r, description=STATIC_ROLES[r]))
