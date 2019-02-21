"""Validate and correct any QuestionnaireResponses needing attention

Revision ID: 69af4bd9ac9a
Revises: a1de3ab4d050
Create Date: 2019-02-21 12:23:53.525121

"""
import copy
from flask import current_app
from flask_swagger import swagger
import jsonschema
import sys

from portal.database import db
from portal.system_uri import DECISION_SUPPORT_GROUP
from portal.models.audit import Audit
from portal.models.user import User
from portal.models.questionnaire_response import QuestionnaireResponse

# revision identifiers, used by Alembic.
revision = '69af4bd9ac9a'
down_revision = 'a1de3ab4d050'


def validate_closure():
    """redefine QuestionnaireResponse.validate_document for efficient loop"""
    swag = swagger(current_app)

    draft4_schema = {
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'type': 'object',
        'definitions': swag['definitions'],
    }

    validation_schema = 'QuestionnaireResponse'
    # Copy desired schema (to validate against) to outermost dict
    draft4_schema.update(swag['definitions'][validation_schema])
    def validate(document, display_stack=False):
        try:
            jsonschema.validate(document, draft4_schema)
            return True
        except jsonschema.ValidationError as e:
            if display_stack:
                sys.stderr.write(str(e))
            return False

    return validate


def lookup_system(label):
    """fabricate a system from the identifier label"""
    if label.startswith('WiserCare'):
        return DECISION_SUPPORT_GROUP + '-wisercare'
    raise ValueError("unknown identifer label {}".format(label))


def correct_invalid_document(qnr_id, validate_fn, sys_id):
    """Attempt to fix the invalid structure of a QNR.document

    Many current QNRs are invalid as a user submitted w/o the `answer` list
    as requires in FHIR DSTU2 QuestionnaireResponse.

    Commits fix and audit row to db

    """
    qnr = QuestionnaireResponse.query.get(qnr_id)
    document = copy.deepcopy(qnr.document)
    answer_list = document['group']
    if not answer_list:
        raise ValueError("no answers under group for {}".format(qnr_id))

    # each answer is to be a list of value_x_ objects
    # nest in a list
    for a in answer_list:
        the_answer = a['answer']

        # remove bogus 'system' at wrong level
        the_answer.pop('system', None)

        # correct string version of numbers
        if 'valueCoding' in the_answer and 'extension' in the_answer[
            'valueCoding']:
            the_answer['valueCoding']['extension']['valueDecimal'] = int(
                the_answer['valueCoding']['extension']['valueDecimal'])

        # put single answer item in list as required
        if not isinstance(the_answer, list):
            a['answer'] = [the_answer]
        else:
            a['answer'] = the_answer

    # put the answer list under the required dict key 'question'
    document['group'] = {'question': answer_list}

    # fix broken identifiers - requires system
    if 'identifier' in document and 'system' not in document['identifier']:
        system = lookup_system(document['identifier']['label'])
        document['identifier']['system'] = system

    # confirm it now validates
    if not validate_fn(document, display_stack=True):
        sys.stderr.write("ERROR - {} is still invalid".format(qnr_id))

    # create audit trail
    comment = (
        "Migration: corrected questionnaire_response.id {} ; "
        "from ill formed document {}".format(qnr_id, qnr.document))
    audit = Audit(
        user_id=sys_id, subject_id=qnr.subject_id, _context='assessment',
        comment=comment)
    db.session.add(audit)

    # replace invalid with now valid document
    qnr.document = document


def upgrade():
    """Iterate over all QNRs, validating and patching any that failed"""

    ids_to_patch = []
    validate = validate_closure()
    sys.stderr.write("invalid QNR.ids: ")
    for qnr in QuestionnaireResponse.query.all():
        if not validate(qnr.document):
            if 'question' in qnr.document['group']:
                sys.stderr.write(
                    "question already in group, can't fix {}".format(qnr.id))
                continue
            ids_to_patch.append(qnr.id)
            sys.stderr.write(" {}".format(qnr.id))
        else:
            sys.stdout.write('.')
            sys.stdout.flush()

    sys_user = User.query.filter_by(email='__system__').first()
    sys_id = sys_user.id

    for id in ids_to_patch:
        correct_invalid_document(id, validate, sys_id)

    db.session.commit()


def downgrade():
    """ don't restore """
    pass
