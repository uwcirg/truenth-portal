"""QBD (Questionnaire Bank Details) Module"""
from ..date_tools import FHIR_datetime
from ..system_uri import TRUENTH_IDENTITY_SYSTEM


class QBD(object):
    """Details needed to define a QB"""

    def __init__(
            self, relative_start, iteration, recur=None, recur_id=None,
            questionnaire_bank=None, qb_id=None):
        """Hold details needed to uniquely define a QB visit

        For db objects ``questionnaire_bank`` and ``recur``, provide either
        the id or object version of each, not both.  If the other is requsted,
        it'll be looked up and cached.

        :param relative_start: UTC datetime value marking start point for QBD
        :param iteration: None w/o a recurrence, otherwise a zero indexed int
        :param recur: If the qb has one or more recurrences, set to the correct
          recurrence, or alternatively pass a ``recur_id`` value.
        :param recur_id: foreign key value for recur, if object not at hand
        :param questionnaire_bank: The QB for the QBD, or alternatively pass
          a ``qb_id`` value.
        :param qb_id: foreign key value for the questionnaire_bank

        """
        if recur and recur_id:
            raise ValueError("expect *either* recur itself or id, not both")
        if questionnaire_bank and qb_id:
            raise ValueError("expect *either* QB itself or id, not both")
        self.relative_start = relative_start
        self.iteration = iteration
        self._recur = recur
        self.recur_id = recur.id if recur else recur_id
        self._questionnaire_bank = questionnaire_bank
        self.qb_id = questionnaire_bank.id if questionnaire_bank else qb_id

    @property
    def recur(self):
        from .recur import Recur
        if not self._recur and self.recur_id is not None:
            self._recur = Recur.query.get(self.recur_id)
        return self._recur

    @property
    def questionnaire_bank(self):
        from .questionnaire_bank import QuestionnaireBank
        if not self._questionnaire_bank and self.qb_id is not None:
            self._questionnaire_bank = QuestionnaireBank.query.get(self.qb_id)
        return self._questionnaire_bank

    @questionnaire_bank.setter
    def questionnaire_bank(self, qb):
        self.qb_id = qb.id
        self._questionnaire_bank = qb

    @property
    def questionnaire_instruments(self):
        return set(q.name for q in self.questionnaire_bank.questionnaires)

    def as_json(self):
        from ..models.questionnaire_bank import visit_name

        results = {}
        results['questionnaire_bank'] = (
            self.questionnaire_bank.as_json()
            if self.questionnaire_bank else None)
        results['relative_start'] = (
            FHIR_datetime.as_fhir(self.relative_start)
            if self.relative_start else None)
        results['iteration'] = self.iteration
        results['visit'] = visit_name(self)
        return results

    def __repr__(self):
        """Useful shortcut in debugging"""
        results = self.as_json()
        qb_name = (
            self._questionnaire_bank.name if self._questionnaire_bank else "")
        return "QBD(visit={visit}, start={rel_start}, qb={qb_name})".format(
            visit=results['visit'],
            rel_start=results['relative_start'],
            qb_name=qb_name,
        )

    def completed_date(self, user_id):
        """Specialized query to return datetime of completion if applicable

        Typically ``QB_Status.completed_date`` can be used, but for arbitrary
        (say historical during reporting lookups) QBDs, execute query
        specifically for the time of completion matching instance (self) data.

        :returns: datetime of completion or None

        """
        from .qb_timeline import QBT
        from .questionnaire_bank import QuestionnaireBank
        from .questionnaire_response import QuestionnaireResponse
        query = QBT.query.filter(QBT.user_id == user_id).filter(
            QBT.qb_id == self.qb_id).filter(
            QBT.qb_recur_id == self.recur_id).filter(
            QBT.qb_iteration == self.iteration).filter(
            QBT.status == 'completed')
        if query.count() > 1:
            raise ValueError(
                f"Should never find multiple completed for {user_id} {self}")
        if not query.count():
            # Check indefinite case, which doesn't generate timeline rows
            if self._questionnaire_bank.classification == 'indefinite':
                found = QuestionnaireResponse.query.filter(
                    QuestionnaireResponse.subject_id == user_id).filter(
                    QuestionnaireResponse.status == 'completed').join(
                    QuestionnaireBank).filter(
                    QuestionnaireResponse.questionnaire_bank_id ==
                    QuestionnaireBank.id).filter(
                    QuestionnaireBank.classification ==
                    'indefinite').with_entities(
                    QuestionnaireResponse.document['authored'].label(
                        'authored')).first()
                if found:
                    return FHIR_datetime.parse(found[0])
            return None
        return query.first().at

    def oow_completed_date(self, user_id):
        """Specialized query to return datetime of oow completion if applicable

        See ``completed_date`` for typical need.  This is specific to
        **out of window** completion, exclusive to when the
        questionnaire_response(s) include the extension used for ``actual``
        completion date.  Actual (out of window) dates should only be
        present on QNRs completed outside of the valid visit window.

        :returns: datetime of actual (out of window) completion or None

        """
        from .questionnaire_response import QuestionnaireResponse

        # Data is only available w/i the QuestionnaireResponses as an extension
        extensions = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == user_id).filter(
            QuestionnaireResponse.status == 'completed').filter(
            QuestionnaireResponse.questionnaire_bank_id ==
            self.qb_id).filter(
            QuestionnaireResponse.qb_iteration ==
            self.iteration).with_entities(
            QuestionnaireResponse.document['extension'].label(
                'extension'))

        # Without supporting JSON/SQLA syntax to filter, must do by hand
        valid_extensions = [r[0] for r in extensions if r[0] is not None]

        # Obtain the latest `actual` date if any matching extensions are found.
        actual = None
        completion_date_system = '/'.join((TRUENTH_IDENTITY_SYSTEM, "actual-completion-date"))
        for extension_lists in valid_extensions:
            for extension in extension_lists:
                if extension.get('url') != completion_date_system:
                    continue
            candidate = FHIR_datetime.parse(extension['valueDateTime'])
            if not actual:
                actual = candidate
            else:
                actual = max(candidate, actual)

        return actual or ''
