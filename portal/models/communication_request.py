"""CommunicationRequest model"""
from datetime import datetime

from flask import current_app
from sqlalchemy import Enum, UniqueConstraint

from ..database import db
from ..date_tools import RelativeDelta
from ..system_uri import TRUENTH_CR_NAME
from ..trace import trace
from .communication import Communication
from .identifier import Identifier
from .overall_status import OverallStatus
from .reference import Reference

# https://www.hl7.org/fhir/valueset-request-status.html
request_status_types = Enum(
    'draft', 'active', 'suspended', 'cancelled', 'completed',
    'entered-in-error', 'unknown', name='request_statuses',
    create_type=False)


class CommunicationRequest(db.Model):
    """Model representing a FHIR-like CommunicationRequest

    CommunicationRequest is used to capture business rules surrounding
    messages, reminders and other forms of communications.

    As the base event which defines the time often moves due to
    procedures and diagnosis, time deltas are generally persisted
    within the CommunicationRequest rather than a static datetime.

    CommunicationRequests are associated with a set of users by a
    QuestionnaireBank, such that for any user for whom the
    QuestionnaireBank applies, send the communication (unless
    the QuestionnaireBank is completed or expired).

    NB - several exceptions from the FHIR spec exist for this model,
    as the FHIR doesn't well handle time deltas and associations as needed.

    """
    __tablename__ = 'communication_requests'
    id = db.Column(db.Integer, primary_key=True)
    identifiers = db.relationship(
        'Identifier', lazy='dynamic',
        secondary="communication_request_identifiers")
    status = db.Column('status', request_status_types, nullable=False)
    notify_post_qb_start = db.Column(
        db.Text, nullable=False,
        doc=("'relativedelta' value (i.e. {\"months\": 3, \"days\": -14}) "
             "from associated Questionnaire Bank start time"))

    questionnaire_bank_id = db.Column(
        db.ForeignKey('questionnaire_banks.id'), nullable=False)
    questionnaire_bank = db.relationship('QuestionnaireBank')
    qb_iteration = db.Column(
        db.Integer(), nullable=True,
        doc=("For recurring QuestionnaireBank association, the "
             "iteration_count this CommunicationRequest applies to"))
    lr_uuid = db.Column(db.Text, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            questionnaire_bank_id, notify_post_qb_start, qb_iteration,
            name='_communication_request_qb_days'),
    )

    def __str__(self):
        description = (
            'CommunicationRequest for {0.questionnaire_bank}'
            ' on {0.notify_post_qb_start}'.format(self))
        if self.qb_iteration is not None:
            description += ' iteration {0.qb_iteration}'.format(self)
        return description

    @property
    def name(self):
        # Specific identifier is used as shorthand for name
        for id in self.identifiers:
            if id.system == TRUENTH_CR_NAME:
                return id.value
        return None

    @property
    def content_url(self):
        """Convert Liferay UUID to full request URL"""
        return (
            "{config[LR_ORIGIN]}/c/portal/truenth/asset/"
            "mail?version=latest&uuid={uuid}".format(
                config=current_app.config, uuid=self.lr_uuid))

    @classmethod
    def find_by_identifier(cls, identifier):
        """Query method to lookup by identifier"""
        c_ids = CommunicationRequestIdentifier.query.filter(
            CommunicationRequestIdentifier.identifier_id == identifier.id
        )
        if c_ids.count() > 1:
            raise ValueError(
                "Multiple CommunicationRequests mapped to {}".format(
                    identifier
                ))
        elif c_ids.count():
            first = c_ids.first()
            return cls.query.get(first.communication_request_id)

    @classmethod
    def from_fhir(cls, data):
        instance = cls()
        return instance.update_from_fhir(data)

    def update_from_fhir(self, data):
        if 'identifier' in data:
            # track current identifiers - must remove any not requested
            remove_if_not_requested = [i for i in self.identifiers]
            for id in data['identifier']:
                identifier = Identifier.from_fhir(id).add_if_not_found()
                if identifier not in self.identifiers.all():
                    self.identifiers.append(identifier)
                else:
                    remove_if_not_requested.remove(identifier)
            for obsolete in remove_if_not_requested:
                self.identifiers.remove(obsolete)
        self.status = data['status']
        self.notify_post_qb_start = data['notify_post_qb_start']
        RelativeDelta.validate(self.notify_post_qb_start)
        self.questionnaire_bank_id = Reference.parse(
            data['questionnaire_bank']).id
        if 'qb_iteration' in data:
            self.qb_iteration = data['qb_iteration']
        self.lr_uuid = data['lr_uuid']
        self = self.add_if_not_found(commit_immediately=True)
        return self

    def as_fhir(self):
        d = {}
        d['resourceType'] = 'CommunicationRequest'
        if self.identifiers.count():
            d['identifier'] = []
        for id in self.identifiers:
            d['identifier'].append(id.as_fhir())
        d['status'] = self.status
        d['notify_post_qb_start'] = self.notify_post_qb_start
        d['questionnaire_bank'] = (
            Reference.questionnaire_bank(
                self.questionnaire_bank.name).as_fhir() if
            self.questionnaire_bank else None)
        if self.qb_iteration is not None:
            d['qb_iteration'] = self.qb_iteration
        d['lr_uuid'] = self.lr_uuid
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, adds new if not found.

        @return: the new or matched CommunicationRequest

        """
        if self.identifiers.count() == 1:
            existing = CommunicationRequest.find_by_identifier(self.identifiers.first())
        else:
            existing = CommunicationRequest.query.filter(
                CommunicationRequest.questionnaire_bank_id ==
                self.questionnaire_bank_id
            ).filter(
                CommunicationRequest.notify_post_qb_start ==
                self.notify_post_qb_start
            ).filter(
                CommunicationRequest.qb_iteration ==
                self.qb_iteration
            ).first()
        if not existing:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        else:
            self.id = existing.id
        self = db.session.merge(self)
        return self


class CommunicationRequestIdentifier(db.Model):
    """link table for CommunicationRequest : n identifiers"""
    __tablename__ = 'communication_request_identifiers'
    id = db.Column(db.Integer, primary_key=True)
    communication_request_id = db.Column(db.ForeignKey(
        'communication_requests.id', ondelete='cascade'), nullable=False)
    identifier_id = db.Column(db.ForeignKey(
        'identifiers.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint(
        'communication_request_id', 'identifier_id',
        name='_communication_request_identifier'),)


def queue_outstanding_messages(user, questionnaire_bank, iteration_count):
    """Lookup and queue any outstanding communications

    Complex task, to determine if a communication should be queued.  Only
    queue if a matching communication doesn't exist, user meets
    preconditions defining event start, and hasn't yet fulfilled the point of
    the communication (such as having completed a questionnaire for which this
    communication is reminding them to do). And then of course, only
    if the notify_days_after_event have passed.

    Messages are queued by adding to the Communications table, with
    'preparation' status.

    """
    if not user.email_ready()[0]:
        # don't queue/send message if user isn't ready to receive them
        trace("user isn't 'email_ready, abort")
        return

    trace("process {}; iteration {}".format(
        questionnaire_bank, iteration_count))

    def existing_communication(user_id, communication_request_id):
        """Return a matching communication, if found"""
        existing = Communication.query.filter(
            Communication.user_id == user_id
        ).filter(
            Communication.communication_request_id == communication_request_id
        ).first()
        if existing:
            trace('found existing communication for this request')
        return existing

    def unfinished_work(qstats):
        """Return True if user has outstanding work and valid time remains

        Users may have completed all the related questionnaires, or they may
        have failed to do so prior to expiration.

        :returns: True IFF there is remaining work for the user to complete at
        this time

        """
        unfinished_work = qstats.overall_status in (
            OverallStatus.due, OverallStatus.overdue,
            OverallStatus.in_progress)
        trace('{} unfinished work'.format(
            'found' if unfinished_work else "didn't find"))
        return unfinished_work

    def queue_communication(user, communication_request):
        """Create new communication object in preparation state"""

        if not user.email_ready()[0]:
            raise ValueError(
                "can't send communication to user w/o valid email address")

        communication = Communication(
            user_id=user.id,
            status='preparation',
            communication_request_id=communication_request.id)
        current_app.logger.debug(
            "communication prepared for {}".format(user.id))
        db.session.add(communication)
        trace('added {}'.format(communication))
        return communication

    now = datetime.utcnow()
    from .qb_status import QB_Status
    research_study_id = questionnaire_bank.research_study_id
    qstats = QB_Status(
        user=user,
        research_study_id=research_study_id,
        as_of_date=datetime.utcnow())
    qbd = qstats.current_qbd()
    if not qbd:
        trace("no current QB found, can't continue")
        return
    trace("computed start {} with expiry {} for QB {} iteration {}".format(
        qbd.relative_start,
        qbd.relative_start + RelativeDelta(questionnaire_bank.expired),
        qbd.questionnaire_bank.name, qbd.iteration))

    newly_crafted = []  # holds tuples (notify_date, communication)
    if not len(questionnaire_bank.communication_requests):
        trace("zero communication requests in questionnaire_bank")

    for request in questionnaire_bank.communication_requests:
        trace("process eligible {}".format(request))
        if request.status != 'active':
            trace("found inactive request, skipping")
            continue

        # The interaction counts must match
        if qbd.iteration != request.qb_iteration:
            trace("iteration mismatch, request doesn't apply")
            continue

        # Continue if matching message was already generated
        if existing_communication(
                user_id=user.id,
                communication_request_id=request.id):
            continue

        # Confirm reason for message remains
        if not unfinished_work(qstats):
            continue

        notify_date = qbd.relative_start + RelativeDelta(
            request.notify_post_qb_start)
        if notify_date < now:
            trace(
                "notify_date {} has passed - add communication".format(
                    notify_date))
            newly_crafted.append((
                notify_date,
                queue_communication(user=user, communication_request=request)))
        else:
            trace(
                "notify_date {} hasn't yet come to pass, doesn't apply".format(
                    notify_date))

    # For first pass on users that happen to have a backdated trigger, it's
    # possible for multiple requests to now be valid.  We don't want to flood
    # the user with multiple communications, so mark all but the latest as
    # 'suspended'.
    if len(newly_crafted) > 1:
        # look for newest, defined by largest notify_date
        trace(
            "multiple ({}) communications generated for single qb - mark "
            "all but one 'suspended'".format(len(newly_crafted)))
        newest = newly_crafted[0]
        for d, c in newly_crafted[1:]:
            if d > newest[0]:
                newest = (d, c)
        for _, c in newly_crafted:
            if c != newest[1]:
                c.status = 'suspended'

    if newly_crafted:
        db.session.commit()
