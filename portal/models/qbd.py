"""QBD (Questionnaire Bank Details) Module"""
from ..date_tools import FHIR_datetime


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
        return "QBD(visit={visit}, start={rel_start}, qb={qb_name})".format(
            visit=results['visit'],
            rel_start=results['relative_start'],
            qb_name=self._questionnaire_bank.name if self._questionnaire_bank else "",
        )
