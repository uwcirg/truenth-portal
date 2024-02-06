""" Defines a series of scripts for running server and maintenance

FLASK_APP=manage.py flask --help

(bogus comment line added to triger build)
"""
import copy
from datetime import datetime
import json
import os
import sys

import alembic.config
import click
from flask import url_for
from flask_migrate import Migrate
import redis
import requests
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound

from portal.audit import auditable_event
from portal.date_tools import FHIR_datetime
from portal.config.config_persistence import import_config
from portal.config.site_persistence import SitePersistence
from portal.extensions import db, user_manager
from portal.factories.app import create_app
from portal.models.clinical_constants import add_static_concepts
from portal.models.i18n_utils import (
    build_pot_files,
    compile_pos,
    download_all_translations,
    smartling_download,
    smartling_upload,
)
from portal.models.intervention import add_static_interventions
from portal.models.organization import add_static_organization
from portal.models.qb_timeline import (
    QBT,
    invalidate_users_QBT,
    update_users_QBT,
)
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
    add_static_questionnaire_bank,
)
from portal.models.questionnaire_response import (
    QuestionnaireResponse,
    capture_patient_state,
    present_before_after_state,
)
from portal.models.relationship import add_static_relationships
from portal.models.research_study import (
    BASE_RS_ID,
    add_static_research_studies,
    research_study_id_from_questionnaire,
)
from portal.models.role import ROLE, Role, add_static_roles
from portal.models.url_token import (
    BadSignature,
    SignatureExpired,
    verify_token,
)
from portal.models.user import (
    User,
    flag_test,
    permanently_delete_user,
    suppress_email,
    validate_email,
)
from portal.tasks import (
    celery_beat_health_check,
    celery_beat_health_check_low_priority_queue,
)

app = create_app()

MIGRATIONS_DIR = os.path.join(app.root_path, 'migrations')
migrate = Migrate(app, db, directory=MIGRATIONS_DIR)


def _run_alembic_command(args):
    """Helper to manage working directory and run given alembic commands"""
    # Alembic looks for the alembic.ini file in CWD
    # hop over there and then return to CWD
    cwd = os.getcwd()
    os.chdir(MIGRATIONS_DIR)

    alembic.config.main(argv=args)

    os.chdir(cwd)  # restore cwd


def stamp_db():
    """Run the alembic command to stamp the db with the current head"""
    # if the alembic_version table exists, this db has been stamped,
    # don't update to head, as it would potentially skip steps.
    if db.engine.dialect.has_table(db.engine.connect(), 'alembic_version'):
        return

    _run_alembic_command(['--raiseerr', 'stamp', 'head'])


def upgrade_db():
    """Run any outstanding migration scripts"""
    _run_alembic_command(['--raiseerr', 'upgrade', 'head'])


def flush_cache():
    """Flush redis of all values.

    Cached values may no longer correspond with new DB entries.
    NB this may incur a significant performance hit as all cached
    entries will be invalidated.

    """
    if app.config.get('FLUSH_CACHE_ON_SYNC'):
        r = redis.from_url(app.config['REDIS_URL'])
        r.flushdb()


@app.cli.command()
def last_usage():
    """Returns number of seconds since last usage was recorded

    NB in the event of no recorded usage, such as after a redis flush
    a value of -1 will be returned

    """
    from portal.usage_monitor import last_usage
    seconds_old = last_usage() or -1
    click.echo(seconds_old)


@app.cli.command()
def sync():
    """Synchronize database with latest schema and persistence data.

    Idempotent function takes necessary steps to build tables, migrate
    schema and run `seed`.  Safe to run on existing or brand new databases.

    To re/create the database, [delete and] create within the DBMS itself,
    then invoke this function.
    """
    if not db.engine.dialect.has_table(db.engine.connect(), 'alembic_version'):
        db.create_all()
    stamp_db()
    flush_cache()
    upgrade_db()
    seed()


@click.option(
    '--keep_unmentioned', '-k', default=False,
    help='Keep orgs and interventions not mentioned in persistence file')
@app.cli.command(name="seed")
def seed_command(keep_unmentioned):
    """Seed database with required data"""
    seed(keep_unmentioned)


def seed(keep_unmentioned=False):
    """Actual seed function

    NB this is defined separately so it can also be called internally,
    i.e. from sync

    """
    # Request context necessary for generating data from own HTTP APIs
    with app.test_request_context():
        add_static_concepts()

    add_static_interventions()
    add_static_organization()
    add_static_questionnaire_bank()
    add_static_relationships()
    add_static_roles()
    add_static_research_studies()
    db.session.commit()

    # import site export file if found
    SitePersistence(target_dir=None).import_(
        keep_unmentioned=keep_unmentioned)


@app.cli.command()
def generate_site_cfg():
    """Generate only the site.cfg file via site_persistence

    Typically done via `sync` or `seed`, this option exists for the
    backend job queues to generate the `site.cfg` file to maintain
    consistent configuration with the front end, withou the overhead
    of the rest of `sync`
    """
    app.logger.info("generate-site-cfg begin")
    import_config(target_dir=None)
    app.logger.info("generate-site-cfg complete")


@click.option('--directory', '-d', default=None, help="Export directory")
@click.option(
    '--staging_exclusion', '-x', default=False, is_flag=True,
    help="Staging Exclusions Export")
@app.cli.command()
def export_site(directory, staging_exclusion):
    """Generate JSON file containing dynamic site config

    :param directory: used to name a non-default target directory for export
      files
    :param staging_exclusion: set only if persisting exclusions to retain
      on staging when pulling over production data.

    Portions of site configuration live in the database, such as
    Organizations and Access Strategies.  Generate a single export
    file for migration of this data to other instances of the service.

    NB the seed command imports the data file if found, along with
    other static data.

    """
    if staging_exclusion and not directory:
        directory = app.config.get("PERSISTENCE_EXCLUSIONS_DIR")

    SitePersistence(target_dir=directory).export(
        staging_exclusion=staging_exclusion)


@click.option('--directory', '-d', default=None, help="Import directory")
@app.cli.command()
def import_site_exclusions(directory):
    """Import serialized exclusions (saved on stage prior to prod db overwrite)

    :param directory: used to name a non-default target directory for import
      files

    """
    if not directory:
        directory = app.config.get("PERSISTENCE_EXCLUSIONS_DIR")

    SitePersistence(target_dir=directory).import_(
        staging_exclusion=True, keep_unmentioned=True)


@click.option('--email', '-e', help="email address for new user")
@click.option('--role', '-r', help="Comma separated role(s) for new user")
@click.option('--password', '-p', help="password for new user")
@app.cli.command()
def add_user(email, role, password):
    """Add new user as specified """
    validate_email(email)
    if not password or len(str(password)) < 5:
        raise ValueError("requires a password")

    pw = user_manager.hash_password(password)
    user = User(email=email, password=pw)
    db.session.add(user)
    roles = role.split(',') if role else []
    try:
        role_list = [
            Role.query.filter_by(name=r).one() for r in roles]
        user.update_roles(role_list, acting_user=user)
    except NoResultFound:
        raise ValueError(
            "one or more roles ill defined {}".format(roles))

    db.session.commit()
    auditable_event(
        "new account generated (via cli) for {}".format(user),
        user_id=user.id, subject_id=user.id, context='account')


def get_actor(actors_email, require_admin=False, editable_ids=None):
    """Helper to query for acting user by email and confirm access

    :param actors_email: email address of acting user to lookup
    :param require_admin: set true if actor must be an admin
    :param editable_ids: optional list of patient ids actor is allowed to edit

    :raises: if actor isn't found or lacks parameterized access
    """
    try:
        acting_user = User.query.filter(
            func.lower(User.email) == actors_email.lower()).one()
    except NoResultFound:
        raise ValueError("email for acting user <{}> not found".format(actors_email))

    if require_admin and not acting_user.has_role(ROLE.ADMIN.value):
        raise ValueError("Actor must be an admin")
    for others_id in editable_ids or []:
        acting_user.check_role(permission='edit', other_id=others_id)

    return acting_user


def get_target(id=None, email=None, error_label="target"):
    """Helper to get target user by id or email address

    :param id: define if known for lookup, or use email
    :param email: define for lookup, or use id
    :param error_label: used in exception text if user isn't found

    :raises ValueError: if not found
    :returns: User object
    """
    if (id and email) or not (id or email):
        raise ValueError("define exactly one of `id` and `email`")

    try:
        if id:
            target_user = User.query.get(id)
        else:
            target_user = User.query.filter(
                func.lower(User.email) == email.lower()).one()
    except NoResultFound:
        raise ValueError(f"{error_label} user not found")
    return target_user


@click.option('--email', '-e', help="target user email for password reset")
@click.option('--password', '-p', help="new password")
@click.option(
    '--actor', '-a',
    help='Email of user taking this action (must be admin)'
)
@app.cli.command()
def password_reset(email, password, actor):
    """Reset given user's password """
    acting_user = get_actor(actor, require_admin=True)
    target_user = get_target(email=email)
    if not password or len(str(password)) < 8:
        raise ValueError("requires a valid password")

    target_user.password = user_manager.hash_password(password)
    db.session.commit()
    auditable_event(
        "cli password reset for {}".format(target_user),
        user_id=acting_user.id, subject_id=target_user.id, context='account')


@click.option('--email', '-e', help='Email of user to purge.')
@click.option(
    '--actor', '-a',
    help='Email of user to act as.',
    prompt=(
        "\n\nWARNING!!!\n\n"
        " This will permanently delete the target user and all their related"
        " data.\n"
        " If you want to continue,"
        " enter a valid user email as the acting party for our records")
)
@app.cli.command()
def purge_user(email, actor):
    """Purge the given user from the system"""
    permanently_delete_user(email, actor=actor)


@click.argument('token')
@app.cli.command()
def token_details(token):
    valid_seconds = app.config.get(
        'TOKEN_LIFE_IN_DAYS') * 24 * 3600
    try:
        user_id = verify_token(token, valid_seconds)
    except SignatureExpired:
        click.echo("EXPIRED token (older than {} seconds)".format(
            valid_seconds))
    except BadSignature:
        click.echo("INVALID token")
    else:
        click.echo("Valid token for user_id {}".format(user_id))


@app.cli.command()
def mark_test():
    """Designate all current users as test users"""
    flag_test()


@app.cli.command()
def compile_po_files():
    """Compile PO files to MO files"""
    compile_pos()
    click.echo("Compiled backend PO files to MO files")


@app.cli.command()
def translation_upload():
    """Update .pot file on Smartling

    Creates a new .pot file, updates the file with relevant DB entries, then
    POSTs said .pot file to Smartling via their API
    """
    smartling_upload()


@app.cli.command()
def extract_i18n():
    """Update .pot file on Smartling

    Creates a new .pot file, updates the file with relevant DB entries
    """
    build_pot_files()


@click.option('--language', '-l', help='language code (e.g. en_US).')
@click.option('--state', '-s', help='Translation state', type=click.Choice([
    'pseudo',
    'pending',
    'published',
    'contextMatchingInstrumented',
]))
@app.cli.command()
def translation_download(language, state):
    """Download .po file(s) from Smartling

    GETs the .po file for the specified language from Smartling via their API.
    If no language is specified, all available translations will be downloaded.
    After download, .po file(s) are compiled into .mo file(s) using pybabel
    """

    default_state = 'pending'
    if app.config['SYSTEM_TYPE'].lower() == 'production':
        default_state = 'published'
    state = state or default_state
    click.echo(
        'Downloading {state} translations from Smartling'.format(state=state))
    smartling_download(state=state, language=language)


@click.option('--state', '-s', help='Translation state', type=click.Choice([
    'pseudo',
    'pending',
    'published',
    'contextMatchingInstrumented',
]))
@app.cli.command()
def download_translations(state):
    default_state = 'pending'
    if app.config['SYSTEM_TYPE'].lower() == 'production':
        default_state = 'published'
    state = state or default_state
    click.echo(
        'Downloading {state} translations from every Smartling project'.format(state=state)
    )
    download_all_translations(state=state)


@click.option(
    '--config_key',
    '-c',
    help='Return a single config value, or empty string if value is None'
)
@app.cli.command()
def config(config_key):
    """List current flask configuration values in JSON"""

    if config_key:
        # Remap None values to an empty string
        print(app.config.get(config_key, '') or '')
        return
    print(json.dumps(
        # Skip un-serializable values
        {k: v for k, v in app.config.items() if isinstance(v, str)},
        indent=2,
    ))


@app.cli.command()
def set_celery_beat_healthy():
    return (
        celery_beat_health_check() and
        celery_beat_health_check_low_priority_queue())


@app.cli.command()
def healthcheck():
    """Calls the healthcheck API"""
    result = requests.get(
        url_for('check')
    )
    print(json.dumps(result.json(), indent=4))

    # Return success (0) if passing status code
    if result.ok:
        return sys.exit()

    # Healthcheck failed. Return a failing status code
    return sys.exit(result.status_code)


@click.option('--email', '-e', help='Email address wanting no communication')
@click.option(
    '--actor', '-a',
    help='email address of user taking this action, for audit trail'
)
@app.cli.command()
def no_email(email, actor):
    """Suppress all future emails for user (beyond p/w reset)"""
    suppress_email(email, actor)


@click.option('--qnr_id', help="Questionnaire Response ID", required=True)
@click.option(
    '--authored',
    required=True,
    help="new datetime for qnr authored, format example: 2019-04-09 15:14:43")
@click.option(
    '--actor',
    required=True,
    help='email address of user taking this action, for audit trail'
)
@app.cli.command()
def update_qnr_authored(qnr_id, authored, actor):
    """Modify authored date on given Questionnaire Response ID"""
    qnr = QuestionnaireResponse.query.get(qnr_id)
    if not qnr:
        raise ValueError(f"Questionnaire Response {qnr_id} not found")

    acting_user = get_actor(actor, editable_ids=[qnr.subject_id])
    document = copy.deepcopy(qnr.document)
    new_authored = FHIR_datetime.parse(authored)
    old_authored = FHIR_datetime.parse(document['authored'])
    document['authored'] = datetime.strftime(new_authored, "%Y-%m-%dT%H:%M:%SZ")
    qnr.document = document

    # Determine research study if qb_id is currently set, default to 0
    rs_id = 0
    if qnr.questionnaire_bank_id:
        qb = QuestionnaireBank.query.get(qnr.questionnaire_bank_id)
        rs_id = research_study_id_from_questionnaire(
            qb.questionnaires[0].name)

    # Must clear the qb_id and iteration in case this authored date
    # change moves the QNR to a different visit.
    qnr.questionnaire_bank_id = None
    qnr.qb_iteration = None
    db.session.commit()

    # Invalidate timeline as this probably altered the status
    invalidate_users_QBT(qnr.subject_id, research_study_id=rs_id)

    message = (
        "Updated QNR {qnr_id} authored from {old_authored} to "
        "{new_authored}".format(
            qnr_id=qnr_id, old_authored=old_authored,
            new_authored=new_authored))
    auditable_event(
        message=message,
        context="assessment",
        user_id=acting_user.id,
        subject_id=qnr.subject_id)
    print(message)


@click.option('--qnr_id', help="Questionnaire Response ID", required=True)
@click.option(
    '--link_id',
    required=True,
    help="linkId to correct, format example: irondemog.27")
@click.option(
    '--actor',
    required=True,
    help='email address of user taking this action, for audit trail'
)
@click.option(
    '--replacement',
    required=False,
    help='JSON snippet for `answer` replacement.  Use --noop result as template'
)
@click.option(
    '--noop',
    is_flag=True,
    show_default=True,
    default=False,
    help='no op, echo current value for requested linkId'
)
@app.cli.command()
def update_qnr(qnr_id, link_id, actor, noop, replacement):
    """Modify given linkId in given Questionnaire Response ID"""
    qnr = QuestionnaireResponse.query.get(qnr_id)
    if not qnr:
        raise ValueError(f"Questionnaire Response {qnr_id} not found")

    old_value = qnr.link_id(link_id)
    if noop:
        if replacement:
            raise ValueError("--noop & --replacement are mutually exclusive")
        click.echo(f"'{json.dumps(old_value)}'")
        return

    new_value = json.loads(replacement)
    acting_user = get_actor(actor, editable_ids=[qnr.subject_id])
    document = copy.deepcopy(qnr.document)
    if set(old_value.keys()) != set(new_value.keys()):
        raise ValueError("inconsistent dictionary keys; can't continue")
    if old_value["text"] != new_value["text"]:
        raise ValueError("question text doesn't match existing; can't continue")
    if old_value["linkId"] != new_value["linkId"]:
        raise ValueError("linkId doesn't match; can't continue")

    questions = qnr.replace_link_id(link_id, new_value)
    document["group"]["question"] = questions
    qnr.document = document
    assert qnr in db.session
    db.session.commit()

    message = (
        f"Updated QNR {qnr_id} {link_id} answer from {old_value['answer']}"
        f" to {new_value['answer']}")
    auditable_event(
        message=message,
        context="assessment",
        user_id=acting_user.id,
        subject_id=qnr.subject_id)
    click.echo(message)


@click.option('--subject_id', type=int, multiple=True, help="Subject user ID", required=True)
@click.option(
    '--actor',
    default="__system__",
    required=False,
    help='email address of user taking this action, for audit trail'
)
@app.cli.command()
def remove_post_withdrawn_qnrs(subject_id, actor):
    """Remove QNRs posted beyond subject's withdrawal date"""
    from sqlalchemy.types import DateTime
    from portal.cache import cache
    from portal.models.questionnaire_bank import trigger_date

    rs_id = 0  # only base study till need arises
    acting_user = get_actor(actor, require_admin=True)

    for subject_id in subject_id:
        # Confirm user has withdrawn
        subject = get_target(id=subject_id)
        study_id = subject.external_study_id

        # Make sure we're not working w/ stale timeline data
        QuestionnaireResponse.purge_qb_relationship(
            subject_id=subject_id,
            research_study_id=rs_id,
            acting_user_id=acting_user.id)
        cache.delete_memoized(trigger_date)
        update_users_QBT(
            subject_id,
            research_study_id=rs_id,
            invalidate_existing=True)

        deceased_date = None if not subject.deceased else subject.deceased.timestamp
        withdrawn_visit = QBT.withdrawn_qbd(subject_id, rs_id)
        if not withdrawn_visit:
            raise ValueError("Only applicable to withdrawn users")

        # Obtain all QNRs submitted beyond withdrawal date
        query = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.document["authored"].astext.cast(DateTime) >
            withdrawn_visit.relative_start
        ).filter(
            QuestionnaireResponse.subject_id == subject_id).with_entities(
            QuestionnaireResponse.id,
            QuestionnaireResponse.questionnaire_bank_id,
            QuestionnaireResponse.qb_iteration,
            QuestionnaireResponse.document["questionnaire"]["reference"].
                label("instrument"),
            QuestionnaireResponse.document["authored"].
                label("authored")
        ).order_by(QuestionnaireResponse.document["authored"])

        for qnr in query:
            # match format in bug report for easy diff
            sub_padding = " "*(11 - len(str(subject_id)))
            stdy_padding = " "*(12 - len(study_id))
            out = (
                f"{sub_padding}{subject_id} | "
                f"{study_id}{stdy_padding}| "
                f"{withdrawn_visit.relative_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}    | "
                f"{qnr.authored} | ")

            # do not include any belonging to the last active visit, unless
            # they came in after deceased date
            if (
                    qnr.questionnaire_bank_id == withdrawn_visit.qb_id and
                    qnr.qb_iteration == withdrawn_visit.iteration and
                    (not deceased_date or FHIR_datetime.parse(
                        qnr.authored) < deceased_date)):
                print(f"{out}keep")
                continue
            if "irondemog" in qnr.instrument:
                print(f"{out}keep (indefinite)")
                continue
            print(f"{out}delete")
            db.session.delete(QuestionnaireResponse.query.get(qnr.id))
            auditable_event(
                message=(
                    "deleted questionnaire response submitted beyond "
                    "withdrawal visit as per request by PCCTC"),
                context="assessment",
                user_id=acting_user.id,
                subject_id=subject_id)
        db.session.commit()
    return


@click.option('--src_id', type=int, help="Source Patient ID (WILL BE DELETED!)")
@click.option('--tgt_id', type=int, help="Target Patient ID")
@click.option(
    '--actor',
    help='email address of user taking this action, for audit trail'
)
@app.cli.command()
def merge_users(src_id, tgt_id, actor):
    """Copy useful portion of source to target user and delete source"""
    from flask import current_app
    from portal.models.audit import Audit
    from portal.models.user import internal_identifier_systems
    from portal.models.tou import ToU

    acting_user = get_actor(actor, editable_ids=[src_id, tgt_id])
    src_user = get_target(id=src_id, error_label="<src_id>")
    tgt_user = get_target(id=tgt_id, error_label="<tgt_id>")

    if not all((src_user, tgt_user)) or (
            src_user.birthdate != tgt_user.birthdate):
        raise ValueError("Birth dates don't match; can't continue")
    if src_user.auth_providers.count() > 0:
        raise ValueError("extend to include auth_providers")

    if src_user.identifiers != tgt_user.identifiers and (
            click.confirm("Add identifiers \n\t{} \nto \n\t{}".format(
                "\n\t".join((str(i) for i in src_user.identifiers if
                             i.system not in internal_identifier_systems)),
                "\n\t".join((str(i) for i in tgt_user.identifiers if
                             i.system not in internal_identifier_systems))))):
        tgt_user.merge_others_relationship(src_user, '_identifiers')

    if src_user.organizations != tgt_user.organizations and (
            click.confirm("Add organizations \n\t{} \nto \n\t{}".format(
                "\n\t".join((str(i) for i in src_user.organizations)),
                "\n\t".join((str(i) for i in tgt_user.organizations))))):
        tgt_user.merge_others_relationship(src_user, 'organizations')

    if src_user.roles != tgt_user.roles:
        only_on_tgt = [r for r in tgt_user.roles if r not in src_user.roles]
        if all((
                i for i in only_on_tgt if i.name in
                current_app.config['PRE_REGISTERED_ROLES'])):
            if click.confirm(
                    "Remove role(s) `{}` only found on target user".format(
                    ",".join((j.name for j in only_on_tgt)))):
                tgt_user.remove_pre_registered_roles()
        else:
            raise ValueError("mismatch on roles beyond pre-registered")

    if src_user.valid_consents != tgt_user.valid_consents and (
            click.confirm("Add consents \n\t{} \nto \n\t{}".format(
                "\n\t".join((str(i) for i in src_user.valid_consents)),
                "\n\t".join((str(i) for i in tgt_user.valid_consents))))):
        tgt_user.merge_others_relationship(src_user, '_consents')

    src_tous = ToU.query.join(Audit).filter(Audit.subject_id == src_user.id)
    tgt_tous = ToU.query.join(Audit).filter(Audit.subject_id == tgt_user.id)
    if src_tous.count() and (
            click.confirm("Add ToUs \n\t{} \nto \n\t{}".format(
                "\n\t".join((str(i) for i in src_tous)),
                "\n\t".join((str(i) for i in tgt_tous))))):
        for tou in src_tous:
            tou.audit.subject_id = tgt_user.id

    if src_user.questionnaire_responses.count() and (
            click.confirm(
                "Add questionnaire_responses \n\t{} \nto \n\t{}".format(
                    "\n\t".join(
                        (str(i) for i in src_user.questionnaire_responses)),
                    "\n\t".join(
                        (str(i) for i in tgt_user.questionnaire_responses))
                ))):
        tgt_user.merge_others_relationship(src_user, 'questionnaire_responses')
        invalidate_users_QBT(tgt_user.id, research_study_id=0)

    src_email = src_user.email  # capture, as it changes on delete
    replace_email = False
    if click.confirm("Replace email {} with {}?".format(
            tgt_user.email, src_email)):
        # must wait till delete_user masks existing
        replace_email = True
    if click.confirm("Replace first name {} with {}".format(
            tgt_user.first_name, src_user.first_name)):
        tgt_user.first_name = src_user.first_name
    if click.confirm("Replace last name {} with {}".format(
            tgt_user.last_name, src_user.last_name)):
        tgt_user.last_name = src_user.last_name
    if click.confirm("Replace password {} with {}".format(
            tgt_user.password, src_user.password)):
        tgt_user.password = src_user.password

    src_user.delete_user(acting_user=acting_user)
    if replace_email:
        tgt_user.email = src_email

    message = "Merged user {} into {} ".format(src_id, tgt_id)
    auditable_event(
        message=message,
        context="account",
        user_id=acting_user.id,
        subject_id=tgt_id)
    print(message)


@app.cli.command()
@click.option(
    '--correct_overlaps', '-c', default=False, is_flag=True,
    help="Correct overlaps moving previous expired prior to subsequent start")
@click.option(
    '--reprocess_qnrs', '-r', default=False, is_flag=True,
    help="When correcting, also reprocess all QNRs for affected patients")
def find_overlaps(correct_overlaps, reprocess_qnrs):
    from portal.models.qb_timeline import check_for_overlaps
    from portal.models.user import patients_query
    admin = get_actor('__system__', require_admin=True)

    query = patients_query(
        acting_user=admin,
        include_test_role=False,
        include_deleted=False)
    for patient in query:
        qbt_rows = QBT.query.filter(
            QBT.user_id == patient.id).filter(
            QBT.research_study_id == BASE_RS_ID).order_by(
            QBT.at, QBT.id).all()
        # Check for overlaps prints out any found with given flag
        if check_for_overlaps(
                qbt_rows, cli_presentation=True) and correct_overlaps:
            # Reprocess w/ adjusting expired, report differences
            b4 = capture_patient_state(patient.id)
            if reprocess_qnrs:
                # Extends runtime and makes for noisy audit logs.
                # Furthermore in practice no QNRs require updates as
                # expiration isn't moved if QNRs were posted in the overlap.
                QuestionnaireResponse.purge_qb_relationship(
                    subject_id=patient.id,
                    research_study_id=0,
                    acting_user_id=admin.id,
                )

            update_users_QBT(
                patient.id, research_study_id=0, invalidate_existing=True)
            present_before_after_state(
                patient.id, patient.external_study_id, b4)


@click.option('--org_id', help="Organization (site) ID", required=True)
@click.option(
    '--retired',
    required=True,
    help="datetime for site's current protocol expiration,"
         " format example: 2019-04-09 15:14:43  or the string 'none'"
         " to generate patient differences without RP change")
@app.cli.command()
def preview_site_update(org_id, retired):
    """Preview Timeline changes for affected users

    As research protocol changes can affect patients' timeline (for example
    if the new protocol overlaps with visits, i.e. quarterly time points,
    and user's submission prevents inclusion of new overlapped visits),
    capture the organization's patients' timeline state before and after the
    protocol change, and generate a diff report.

    """
    from portal.models.organization import (
        Organization,
        OrganizationResearchProtocol,
    )
    from portal.models.research_protocol import ResearchProtocol
    from portal.models.user import patients_query

    if app.config['SYSTEM_TYPE'].lower() == 'production':
        raise RuntimeError("Not to be run on prod: changes user records")

    organization = Organization.query.get(org_id)
    admin = get_actor('__system__', require_admin=True)

    query = patients_query(
        acting_user=admin,
        include_test_role=False,
        include_deleted=False,
        requested_orgs=[org_id])

    # Capture state for all potentially affected patients
    patient_state = {}
    for patient in query:
        patient_state[patient.id] = capture_patient_state(patient.id)

    new_org_rp = None
    if retired.lower() != 'none':
        # Update the org's research protocol as requested - assume to the latest
        previous_rp = organization.research_protocols[-1]
        assert previous_rp.name == 'IRONMAN v3'
        latest_rp = ResearchProtocol.query.filter(
            ResearchProtocol.name == 'IRONMAN v5').one()
        previous_org_rp = OrganizationResearchProtocol.query.filter(
            OrganizationResearchProtocol.research_protocol_id ==
            previous_rp.id).filter(
            OrganizationResearchProtocol.organization_id == org_id).one()
        previous_org_rp.retired_as_of = retired
        new_org_rp = OrganizationResearchProtocol(
            research_protocol=latest_rp,
            organization=organization)
        db.session.add(new_org_rp)
        db.session.commit()
        print(f"Extending Research Protocols for {organization}")
        print(f"  - Adding RP {latest_rp.name}")
        print(f"  - {previous_rp.name} now retired as of {retired}")
        print("-"*80)

    # With new RP in place, cycle through patients, purge and
    # refresh timeline and QNR data, and report any diffs
    total_qnrs, total_qnrs_assigned = 0, 0
    total_qnrs_completed_b4, total_qnrs_completed_after = 0, 0
    total_qbs_completed_b4, total_qbs_completed_after = 0, 0
    patients_with_fewer_assigned = []
    for patient in query:
        QuestionnaireResponse.purge_qb_relationship(
            subject_id=patient.id,
            research_study_id=0,
            acting_user_id=admin.id,
        )
        update_users_QBT(
            patient.id, research_study_id=0, invalidate_existing=True)
        after_qnrs, after_timeline, qnrs_lost_reference, _ = present_before_after_state(
            patient.id, patient.external_study_id, patient_state[patient.id])
        total_qnrs += len(patient_state[patient.id]['qnrs'])
        total_qbs_completed_b4 += len(
            [1 for date_status in patient_state[patient.id]['timeline'].keys()
             if date_status.endswith('Completed') and
             not date_status.endswith('Partially Completed')])
        total_qbs_completed_after += len(
            [1 for date_status in after_timeline.keys()
             if date_status.endswith('Completed') and
             not date_status.endswith('Partially Completed')])
        b4_total = sum(
            [1 for qb_name in patient_state[patient.id]['qnrs'].values()
             if qb_name[0] != "none of the above"])
        total_qnrs_completed_b4 += b4_total
        after_total = sum(
            [1 for qb_name in after_qnrs.values()
             if qb_name[0] != "none of the above"])
        total_qnrs_completed_after += after_total
        if b4_total != after_total:
            patients_with_fewer_assigned.append((patient.id, qnrs_lost_reference))

    print(f"{total_qnrs} QuestionnaireResponses for all patients in organization {org_id}")
    print(organization.name)
    print(f"  Patients in organization: {len(patient_state)}")
    print(f"  Patients negatively affected by change: {len(patients_with_fewer_assigned)}")
    print(f"  Number of those QNRs assigned to a QB before RP change: {total_qnrs_completed_b4}")
    print(f"  Number of those QNRs assigned to a QB after RP change: {total_qnrs_completed_after}")
    print(f"  Number of QuestionnaireBanks completed before RP change: {total_qbs_completed_b4}")
    print(f"  Number of QuestionnaireBanks completed after RP change: {total_qbs_completed_after}")
    print(" Details of patients having lost a QuestionnaireResponse association:")
    for item in patients_with_fewer_assigned:
        print(f"  Patient {item[0]}")
        for qnr_deet in item[1]:
            print(f"    visit: {qnr_deet[0]} questionnaire: {qnr_deet[1]}")

    # Restore organization to pre-test RPs
    if new_org_rp:
        db.session.delete(new_org_rp)
        db.session.commit()
