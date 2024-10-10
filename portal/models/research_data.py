""" model data for questionnaire response 'research data' reports """
from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import UniqueConstraint
import re

from ..database import db
from ..date_tools import FHIR_datetime
from .reference import Reference
from .research_study import research_study_id_from_questionnaire
from .user import User


class ResearchData(db.Model):
    """ Cached adherence report data

    Full history research data is expensive to generate and rarely changes,
    except on receipt of new questionnaire response inserts and updates.

    Cache reportable data in simple JSON structure, maintaining indexed columns
    for lookup and invalidation.
    """
    __tablename__ = 'research_data'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(
        db.ForeignKey('users.id', ondelete='cascade'), index=True, nullable=False)
    questionnaire_response_id = db.Column(
        db.ForeignKey('questionnaire_responses.id', ondelete='cascade'),
        index=True, unique=True, nullable=False,
        doc="source questionnaire response")
    instrument = db.Column(db.Text, index=True, nullable=False)
    research_study_id = db.Column(db.Integer, index=True, nullable=False)
    authored = db.Column(
        db.DateTime, nullable=False, index=True,
        doc="document.authored used for sorting")
    data = db.Column(JSONB)


def cache_research_data(job_id=None, manual_run=None):
    """add all missing questionnaire response rows to research_data table

    The ResearchData table holds a row per questionnaire response, used to
    generate research data reports.  The only exceptions are questionnaire
    responses from deleted users, and questionnaire responses without visit
    (questionnaire bank) associations.

    This routine is called as a scheduled task, to pick up any interrupted
    or overlooked rows.  As questionnaire responses are posted to the system,
    they are added to the cache immediately.
    """
    from .questionnaire_response import QuestionnaireResponse
    deleted_subjects = db.session.query(User.id).filter(User.deleted_id.isnot(None)).subquery()
    already_cached = db.session.query(ResearchData.questionnaire_response_id).subquery()
    qnrs = QuestionnaireResponse.query.filter(
        QuestionnaireResponse.questionnaire_bank_id > 0).filter(
        QuestionnaireResponse.subject_id.notin_(deleted_subjects)).filter(
        QuestionnaireResponse.id.notin_(already_cached))

    current_app.logger.info(
        f"found {qnrs.count()} questionnaire responses missing from research_data cache")
    for qnr in qnrs:
        # research_study_id of None triggers a lookup
        add_questionnaire_response(qnr, research_study_id=None)


def invalidate_qnr_research_data(questionnaire_response):
    """invalidate row for given questionnaire response"""
    ResearchData.query.filter(
        ResearchData.questionnaire_response_id == questionnaire_response.id).delete()
    db.session.commit()


def invalidate_patient_research_data(subject_id, research_study_id):
    """invalidate applicable rows via removal"""
    ResearchData.query.filter(ResearchData.subject_id == subject_id).filter(
        ResearchData.research_study_id == research_study_id).delete()
    db.session.commit()


def update_single_patient_research_data(subject_id):
    """back door to build research data for single patient"""
    from .questionnaire_response import QuestionnaireResponse
    qnrs = QuestionnaireResponse.query.filter(
        QuestionnaireResponse.questionnaire_bank_id > 0).filter(
        QuestionnaireResponse.subject_id == subject_id)
    for qnr in qnrs:
        # research_study_id of None triggers a lookup
        add_questionnaire_response(qnr, research_study_id=None)


def add_questionnaire_response(questionnaire_response, research_study_id):
    """Insert single questionnaire response details into ResearchData table

    :param questionnaire_response: the questionnaire response to add to the cache
    :param research_study_id: the research_study_id, if known.  pass None to force lookup

    """
    from .qb_timeline import qb_status_visit_name

    # TN-3250, don't include QNRs without assigned visits, i.e. qb_id > 0
    if not questionnaire_response.questionnaire_bank_id:
        return

    instrument = questionnaire_response.document['questionnaire']['reference'].split('/')[-1]
    if research_study_id is None:
        research_study_id = research_study_id_from_questionnaire(instrument)

    patient_fields = ("careProvider", "identifier")
    document = questionnaire_response.document_answered.copy()
    subject = questionnaire_response.subject
    document['encounter'] = questionnaire_response.encounter.as_fhir()
    document["subject"] = {
        k: v for k, v in subject.as_fhir().items() if k in patient_fields
    }

    if subject.organizations:
        providers = []
        for org in subject.organizations:
            org_ref = Reference.organization(org.id).as_fhir()
            identifiers = [i.as_fhir() for i in org.identifiers if i.system == "http://pcctc.org/"]
            if identifiers:
                org_ref['identifier'] = identifiers
            providers.append(org_ref)
        document["subject"]["careProvider"] = providers

    qb_status = qb_status_visit_name(
        subject.id,
        research_study_id,
        FHIR_datetime.parse(questionnaire_response.document['authored']))
    document["timepoint"] = qb_status['visit_name']

    research_data = ResearchData(
        subject_id=subject.id,
        questionnaire_response_id=questionnaire_response.id,
        instrument=instrument,
        research_study_id=research_study_id,
        authored=FHIR_datetime.parse(document['authored']),
        data=document
    )
    db.session.add(research_data)
    db.session.commit()
