"""Patient API - implements patient specific views such as patient search

NB - this is not to be confused with 'patients', which defines views
for staff

"""
from collections import defaultdict
from datetime import datetime
import json

from flask import Blueprint, Response, abort, current_app, jsonify, request
from sqlalchemy import and_
from werkzeug.exceptions import Unauthorized

from ..audit import auditable_event
from ..cache import cache
from ..database import db
from ..date_tools import FHIR_datetime, as_fhir
from ..extensions import oauth
from ..models.adherence_data import sorted_adherence_data
from ..models.communication import Communication
from ..models.fhir import bundle_results
from ..models.identifier import (
    Identifier,
    UserIdentifier,
    parse_identifier_params,
)
from ..models.message import EmailMessage
from ..models.overall_status import OverallStatus
from ..models.qb_timeline import QBT, invalidate_users_QBT, update_users_QBT
from ..models.questionnaire_bank import QuestionnaireBank, trigger_date
from ..models.questionnaire_response import QuestionnaireResponse
from ..models.reference import Reference
from ..models.research_study import (
    ResearchStudy,
    research_study_id_from_questionnaire
)
from ..models.role import ROLE
from ..models.user import User, current_user, get_user
from ..models.user_consent import consent_withdrawal_dates
from ..timeout_lock import ADHERENCE_DATA_KEY, CacheModeration
from .crossdomain import crossdomain
from .demographics import demographics

patient_api = Blueprint('patient_api', __name__)


@patient_api.route('/api/patient/')
@crossdomain()
@oauth.require_oauth()
def patient_search():
    """Looks up patient(s) from given parameters, returns FHIR Patient bundle

    Takes key=value pairs to look up.  Email, identifier searches supported.

    Example searches:
        /api/patient/?email=username@server.com
        /api/patient/?identifier=http://us.truenth.org/identity-codes/external-study-id|123-45-678

    Identifier search pattern:
        ?identifier=<system>|<value>

    Deleted users and users for which the authenticated user does not have
    permission to view will NOT be included in the results.

    NB - the results are restricted to users with the patient role.  It is
    therefore possible to get no results from this and still see a unique email
    collision from existing non-patient users.

    NB - currently out of FHIR DSTU2 spec by default.  Include query string
    parameter ``patch_dstu2=True`` to properly return a FHIR bundle resource
    (https://www.hl7.org/fhir/DSTU2/bundle.html) naming the ``total`` matches
    and references to all matching patients.  With ``patch_dstu2=True``, the
    total will be zero if no matches are found, whereas the default (old,
    non-compliant) behavior is to return a 404 when no match is found.
    Please consider using the ``patch_dstu2=True`` parameter, as this will
    become the default behavior in the future.

    Returns a FHIR bundle resource (https://www.hl7.org/fhir/DSTU2/bundle.html)
    formatted in JSON for all matching valid, accessible patients, with
    ``patch_dstu2=True`` set (preferred).  Default returns single patient on a
    match, 404 on no match, and 400 for multiple as it's not supported.

    ---
    tags:
      - Patient
    operationId: patient_search
    produces:
      - application/json
    parameters:
      - name: search_parameters
        in: query
        description:
            Search parameters, such as `email` or `identifier`.  For
            identifier, URL-encode the `system` and `value` using '|' (pipe)
            delimiter, i.e. `api/patient/?identifier=http://fake.org/id|12a7`
        required: true
        type: string
      - name: patch_dstu2
        in: query
        description: whether or not to return DSTU2 compliant bundle
        required: false
        type: boolean
        default: false
    responses:
      200:
        description:
          Returns FHIR patient resource
          (https://www.hl7.org/fhir/DSTU2/patient.html) in JSON if a match
          is found.  Otherwise responds with a 404 status code.
      401:
        description:
          if missing valid OAuth token
      404:
        description:
          if there is no match found, or the user lacks permission to look
          up details on the match.
    security:
      - ServiceToken: []

    """
    if not request.args.items():
        abort(400, "missing search criteria")

    query = User.query.filter(User.deleted_id.is_(None))
    for k, v in request.args.items():
        if k == 'email':
            query = query.filter(User.email == v)
        elif k == 'identifier':
            system, value = parse_identifier_params(v)
            if not (system and value):
                abort(400, "need 'system' and 'value' to look up identifier")

            query = query.join(UserIdentifier).join(
                Identifier).filter(and_(
                    UserIdentifier.identifier_id == Identifier.id,
                    Identifier.system == system,
                    Identifier._value == value))
        elif k == 'patch_dstu2':
            # not search criteria, but valid
            continue
        else:
            abort(400, "can't search on '{}' at this time".format(k))

    # Validate permissions to see every requested user - omitting those w/o
    patients = []
    for user in query:
        try:
            current_user().check_role(permission='view', other_id=user.id)
            if user.has_role(ROLE.PATIENT.value):
                patients.append(
                    {'resource': Reference.patient(user.id).as_fhir()})
        except Unauthorized:
            # Mask unauthorized as a not-found.  Don't want unauthed users
            # farming information - i.e. don't add to results
            auditable_event("looking up users with inadequate permission",
                            user_id=current_user().id, subject_id=user.id,
                            context='authentication')

    if request.args.get('patch_dstu2', False):
        link = {"rel": "self", "href": request.url}
        return jsonify(bundle_results(elements=patients, links=[link]))
    else:
        # Emulate old results
        if len(patients) == 0:
            abort(404)
        if len(patients) > 1:
            abort(400, "multiple results found, include `patch_dstu2=True`")

        ref = Reference.parse(patients[0]['resource'])
        return demographics(patient_id=ref.id)


@patient_api.route('/api/patient/<int:patient_id>/deceased', methods=('POST',))
@crossdomain()
@oauth.require_oauth()
def post_patient_deceased(patient_id):
    """POST deceased datetime or status for a patient

    This convenience API wraps the ability to set a patient's
    deceased status and deceased date time - generally the /api/demographics
    API should be preferred.

    ---
    operationId: deceased
    tags:
      - Patient
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: deceased_details
          properties:
            deceasedBoolean:
              type: string
              description:
                true or false.  Implicitly true with deceasedDateTime value
            deceasedDateTime:
              type: string
              description: valid FHIR datetime string defining time of death
    responses:
      200:
        description:
          Returns updated [FHIR patient
          resource](http://www.hl7.org/fhir/patient.html) in JSON.
      400:
        description:
          if given parameters don't function, such as a false
          deceasedBoolean AND a deceasedDateTime value.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    patient = get_user(patient_id, 'edit')
    if not request.json or set(request.json.keys()).isdisjoint(
            {'deceasedDateTime', 'deceasedBoolean'}):
        abort(400, "Requires deceasedDateTime or deceasedBoolean in JSON")

    try:
        patient.update_deceased(request.json)
    except ValueError as ve:
        if "Dates prior to year 1900 not supported" in str(ve):
            abort(
                400,
                "deceasedDateTime unrealistically historic (pre-1900),"
                f" please review: {request.json['deceasedDateTime']}")
        else:
            raise ve

    db.session.commit()
    auditable_event("updated demographics on user {0} from input {1}".format(
        patient.id, json.dumps(request.json)), user_id=current_user().id,
        subject_id=patient.id, context='user')

    return jsonify(patient.as_fhir(include_empties=False))


@patient_api.route(
    '/api/patient/<int:patient_id>/birthdate', methods=('POST',))
@patient_api.route(
    '/api/patient/<int:patient_id>/birthDate', methods=('POST',))
@oauth.require_oauth()
def post_patient_dob(patient_id):
    """POST date of birth for a patient

    This convenience API wraps the ability to set a patient's birthDate.
    Generally the /api/demographics API should be preferred.

    ---
    tags:
      - Patient
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: dob_details
          properties:
            birthDate:
              type: string
              description: valid FHIR date string defining date of birth
    responses:
      200:
        description:
          Returns updated [FHIR patient
          resource](http://www.hl7.org/fhir/patient.html) in JSON.
      400:
        description:
          if given parameters don't validate
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to edit requested patient
    security:
      - ServiceToken: []

    """
    patient = get_user(patient_id, 'edit')
    if not request.json or 'birthDate' not in request.json:
        abort(400, "Requires `birthDate` in JSON")

    patient.update_birthdate(request.json)
    db.session.commit()
    auditable_event("updated demographics on user {0} from input {1}".format(
        patient.id, json.dumps(request.json)), user_id=current_user().id,
        subject_id=patient.id, context='user')

    return jsonify(patient.as_fhir(include_empties=False))


@patient_api.route('/api/patient/<int:patient_id>/timeline')
@oauth.require_oauth()
def patient_timeline(patient_id):
    """Display details for the user's Questionnaire Bank Timeline

    Optional query parameters
    :param purge: set 'true' to recreate QBTimeline, 'all' to also reset
      QNR -> QB assignments
    :param research_study_id: set to alternative research study ID - default 0
    :param trace: set 'true' to view detailed logs generated, works best in
      concert with purge
    :param only: set to filter all results but top level attribute given
    :param pretty: set to generate a pretty-printed JSON result

    """
    from ..date_tools import FHIR_datetime, RelativeDelta
    from ..models.organization import (
        UserOrganization,
        OrganizationResearchProtocol,
    )
    from ..models.qbd import QBD
    from ..models.qb_status import QB_Status
    from ..models.questionnaire_bank import translate_visit_name, visit_name
    from ..models.questionnaire_response import aggregate_responses
    from ..models.research_protocol import ResearchProtocol
    from ..tasks import cache_single_patient_adherence_data
    from ..trace import dump_trace, establish_trace

    user = get_user(patient_id, permission='view')
    trace = request.args.get('trace', False)
    if trace:
        establish_trace("BEGIN time line lookup for {}".format(patient_id))

    try:
        research_study_id = int(request.args.get('research_study_id', 0))
    except ValueError:
        abort(400, "integer value required for 'research_study_id'")
    purge = request.args.get('purge', False)
    try:
        # If purge was given special 'all' value, also wipe out associated
        # questionnaire_response : qb relationships and remove cache lock
        # on adherence data.
        if purge == 'all':
            # remove adherence cache key to allow fresh run
            cache_moderation = CacheModeration(key=ADHERENCE_DATA_KEY.format(
                patient_id=patient_id,
                research_study_id=research_study_id))
            cache_moderation.reset()

            QuestionnaireResponse.purge_qb_relationship(
                subject_id=patient_id,
                research_study_id=research_study_id,
                acting_user_id=current_user().id)

        cache.delete_memoized(trigger_date)
        if purge:
            invalidate_users_QBT(user_id=patient_id, research_study_id=research_study_id)
        update_users_QBT(user_id=patient_id, research_study_id=research_study_id)
    except ValueError as ve:
        abort(500, str(ve))

    consents = [
        {"research_study_id": c.research_study_id,
         "acceptance_date": c.acceptance_date,
         "status": c.status} for c in user.valid_consents]
    results = []
    # We order by at (to get the latest status for a given QB) and
    # secondly by id, as on rare occasions, the time (`at`) of
    #  `due` == `completed`, but the row insertion defines priority
    for qbt in QBT.query.filter(QBT.user_id == patient_id).filter(
            QBT.research_study_id == research_study_id).order_by(
            QBT.at, QBT.id):
        # build qbd for visit name
        qbd = QBD(
            relative_start=qbt.at, qb_id=qbt.qb_id,
            iteration=qbt.qb_iteration, recur_id=qbt.qb_recur_id)
        if qbt.status == OverallStatus.withdrawn:
            results.append({
                'status': str(qbt.status),
                'at': FHIR_datetime.as_fhir(qbt.at)})
        else:
            data = {
                'status': str(qbt.status),
                'at': FHIR_datetime.as_fhir(qbt.at),
                'qb (id, iteration)': "{} ({}, {})".format(
                    qbd.questionnaire_bank.name, qbd.qb_id, qbd.iteration),
                'visit': translate_visit_name(visit_name(qbd))}
            if qbt.status == OverallStatus.due:
                data['questionnaires'] = ','.join(
                    [q.name for q in qbd.questionnaire_bank.questionnaires])
                data['expires'] = FHIR_datetime.as_fhir(
                    qbt.at + RelativeDelta(qbd.questionnaire_bank.expired))
            results.append(data)

    qb_names = {qb.id: qb.name for qb in QuestionnaireBank.query.all()}

    qnrs = QuestionnaireResponse.query.filter(
        QuestionnaireResponse.subject_id == patient_id).order_by(
        QuestionnaireResponse.document['authored'])

    def get_recur_id(qnr):
        if qnr.questionnaire_bank and len(qnr.questionnaire_bank.recurs):
            return qnr.questionnaire_bank.recurs[0].id
        return None

    posted = [
        "{}, {}, {} ({}, {}), {}, {}".format(
            qnr.id,
            qnr.document['authored'],
            visit_name(QBD(
                relative_start=None, qb_id=qnr.questionnaire_bank_id,
                iteration=qnr.qb_iteration, recur_id=get_recur_id(qnr))),
            qb_names.get(qnr.questionnaire_bank_id),
            qnr.qb_iteration,
            qnr.status,
            qnr.document['questionnaire']['reference'].split('/')[-1])
        for qnr in qnrs]

    rp_query = ResearchProtocol.query.join(
        OrganizationResearchProtocol,
        OrganizationResearchProtocol.research_protocol_id ==
        ResearchProtocol.id).join(
        UserOrganization,
        UserOrganization.organization_id ==
        OrganizationResearchProtocol.organization_id).filter(
        UserOrganization.user_id == patient_id).with_entities(
        ResearchProtocol.name, OrganizationResearchProtocol.retired_as_of)
    rps = []
    for rp in rp_query:
        msg = rp.name
        if rp.retired_as_of:
            msg = f"{msg}, retired: {rp.retired_as_of}"
        rps.append(msg)

    qbstatus = QB_Status(
        user=User.query.get(patient_id),
        research_study_id=research_study_id,
        as_of_date=datetime.utcnow())
    prev_qbd = qbstatus.prev_qbd
    current = qbstatus.current_qbd()
    next_qbd = qbstatus.next_qbd
    status = {
        'overall': str(qbstatus.overall_status),
        'previous QBD': prev_qbd.as_json() if prev_qbd else None,
        'current QBD': current.as_json() if current else None,
        'next QBD': next_qbd.as_json() if next_qbd else None,
    }
    if current:
        status['due'] = qbstatus.due_date
        status['overdue'] = qbstatus.overdue_date
        status['expired'] = qbstatus.expired_date
        status['needing-full'] = qbstatus.instruments_needing_full_assessment()
        status['in-progress'] = qbstatus.instruments_in_progress()
        status['completed'] = qbstatus.instruments_completed()

    indef_qbd, indef_status = qbstatus.indef_status()
    if indef_qbd:
        status['indefinite QBD'] = indef_qbd.as_json()
        status['indefinite status'] = indef_status

    adherence_data = sorted_adherence_data(patient_id, research_study_id)
    if not adherence_data:
        # immediately following a cache purge, adherence data is gone and
        # needs to be recreated.
        kwargs = {
            "patient_id": user.id,
            "research_study_id": research_study_id,
        }
        cache_single_patient_adherence_data(**kwargs)
        adherence_data = sorted_adherence_data(patient_id, research_study_id)

    agg_args = {
        'instrument_ids': None,
        'current_user': current_user(),
        'patient_ids': [patient_id],
    }
    qnr_responses = aggregate_responses(**agg_args)

    if qnr_responses['total'] == 0:
        from ..models.research_data import update_single_patient_research_data
        update_single_patient_research_data(patient_id)
        qnr_responses = aggregate_responses(**agg_args)

    # filter qnr data to a manageable result data set
    qnr_data = []
    for row in qnr_responses['entry']:
        i = {}
        i['questionnaire'] = row['questionnaire']['reference'].split('/')[-1]

        # qnr_responses return all.  filter to requested research_study
        study_id = research_study_id_from_questionnaire(i['questionnaire'])
        if study_id != research_study_id:
            continue

        i['auth_method'] = row['encounter']['auth_method']
        i['encounter_period'] = row['encounter']['period']
        i['document_authored'] = row['authored']
        try:
            i['ae_session'] = row['identifier']['value']
        except KeyError:
            # happens with sub-study follow up, skip ae_session
            pass
        i['status'] = row['status']
        i['org'] = ': '.join((
            row['subject']['careProvider'][0]['identifier'][0]['value'],
            row['subject']['careProvider'][0]['display']))
        i['visit'] = row['timepoint']
        qnr_data.append(i)

    consent_date, withdrawal_date = consent_withdrawal_dates(user, research_study_id)
    consents = {"consent_date": consent_date, "withdrawal_date": withdrawal_date}
    kwargs = {
        "consents": consents,
        "rps": rps,
        "status": status,
        "posted": posted,
        "timeline": results,
        "adherence_data": adherence_data,
        "qnr_data": qnr_data
    }
    if trace:
        kwargs["trace"] = dump_trace("END time line lookup")

    only = request.args.get('only', False)
    if only:
        if only not in kwargs:
            raise ValueError(f"{only} not in {kwargs.keys()}")
        return jsonify(only, kwargs[only])
    if request.args.get("pretty"):
        pretty_json = json.dumps(kwargs, indent=2, default=as_fhir)
        return Response(pretty_json, mimetype='Application/json')
    return jsonify(**kwargs)


@patient_api.route('/api/patient/<int:patient_id>/timewarp/<int:days>')
@crossdomain()
@oauth.require_oauth()
def patient_timewarp(patient_id, days):
    """Debugging view to time warp patient's data back in time

    :param patient_id: the patient to time warp
    :param days: the number of days to move back - forward moves not supported

    NB: only available on testing and development systems.
    """
    from dateutil.relativedelta import relativedelta
    from copy import deepcopy
    from portal.models.questionnaire_response import QuestionnaireResponse
    from portal.models.user_consent import UserConsent
    from ..trigger_states.models import TriggerState

    def sanity_check():
        """confirm user state before / after timewarp"""
        # User should have one valid consent
        patient = get_user(patient_id, 'view')
        consents = patient.valid_consents
        rps = [c for c in consents if c.research_study_id == 0]
        assert len(rps) == 1

        rp1s = [c for c in consents if c.research_study_id == 1]
        if not len(rp1s):
            return
        assert len(rp1s) == 1

        # Confirm valid trigger_states.  No data prior to consent.
        ts = TriggerState.query.filter(
            TriggerState.user_id == patient_id,
            TriggerState.timestamp < rp1s[0].acceptance_date).count()
        assert ts == 0

        # should never be more than a single row for any given state
        ts = TriggerState.query.filter(
            TriggerState.user_id == patient_id
        )
        data = defaultdict(int)
        for row in ts:
            key = f"{row.visit_month}:{row.state}"
            data[key] += 1
        for k, v in data.items():
            if v > 1:
                raise RuntimeError(
                    f"Unique visit_month:state {k} broken in trigger_states for {patient}")

    sanity_check()
    if current_app.config['SYSTEM_TYPE'] == "production":
        abort(404)

    if days < 1:
        abort(500, 'only possible to move a positive number of days back')
    user = get_user(patient_id, 'edit')

    # user_consent
    changed = []
    delta = relativedelta(days=days)
    for uc in UserConsent.query.filter(UserConsent.user_id == user.id):
        changed.append(f"user_consent {uc.id}")
        uc.acceptance_date = uc.acceptance_date - delta

    # questionnaire_responses
    for qnr in QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == user.id):
        changed.append(f"questionnaire_response {qnr.id}")
        new_authored = FHIR_datetime.parse(qnr.document['authored']) - delta
        doc = deepcopy(qnr.document)
        doc['authored'] = FHIR_datetime.as_fhir(new_authored)
        qnr.document = doc

    # trigger_state
    if current_app.config['GIL'] is None:
        for ts in TriggerState.query.filter(
                TriggerState.user_id == user.id):
            changed.append(f"trigger_state {ts.id}")
            ts.timestamp = ts.timestamp - delta
            if ts.triggers is not None:
                triggers = deepcopy(ts.triggers)
                # Some early records don't include source-authored
                if 'authored' in triggers['source']:
                    triggers['source']['authored'] = FHIR_datetime.as_fhir(
                        FHIR_datetime.parse(triggers['source']['authored'])
                        - delta)
                if 'actions' in triggers:
                    for email in triggers['actions']['email']:
                        email['timestamp'] = FHIR_datetime.as_fhir(
                            FHIR_datetime.parse(email['timestamp']) - delta)
                ts.triggers = triggers

    # reminder email dates
    for em in EmailMessage.query.join(
            Communication, Communication.message_id == EmailMessage.id).filter(
            EmailMessage.recipient_id == user.id):
        changed.append(f'email_message {em.id}')
        em.sent_at = em.sent_at - delta

    # access records in audit
    from ..models.audit import Audit
    query = Audit.query.filter(Audit.subject_id == user.id).filter(
        Audit._context == 'access')
    for ar in query:
        changed.append(f"audit {ar.id}")
        ar.timestamp = ar.timestamp - delta

    db.session.commit()
    sanity_check()

    # Recalculate users timeline & qnr associations
    cache.delete_memoized(trigger_date)
    for research_study_id in ResearchStudy.assigned_to(user):
        QuestionnaireResponse.purge_qb_relationship(
            subject_id=patient_id,
            research_study_id=research_study_id,
            acting_user_id=current_user().id)

        invalidate_users_QBT(user_id=patient_id, research_study_id=research_study_id)
        update_users_QBT(user_id=patient_id, research_study_id=research_study_id)

    auditable_event(
        message=f"TIME WARPED existing data back {days} days.",
        user_id=current_user().id,
        subject_id=patient_id,
        context="assessment"
    )
    return jsonify(changed=changed)
