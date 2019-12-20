"""Module for pre defined procedure codes and shortcuts"""
from ..system_uri import ICHOM, SNOMED, TRUENTH_CLINICAL_CODE_SYSTEM
from .codeable_concept import CodeableConcept
from .coding import Coding
from .lazy import lazyprop


def known_treatment_started(user):
    """Returns True if the user has a procedure suggesting Tx started

    If the user has a procedure suggesting treatment has started, such as
    'Radical prostatectomy' or 'Androgen deprivation therapy' (and several
    others), this function will return True.

    A lack of information will return False, i.e. if user hasn't yet
    set any procedure information.

    """
    cc_ids = set(cc.id for cc in TxStartedConstants())
    has_procs = set(proc.code_id for proc in user.procedures)
    return not cc_ids.isdisjoint(has_procs)


def latest_treatment_started_date(user):
    """Returns most recent performed date for Tx proc, or None

    Look up procedures for given user, returning the most recent
    performed date if any from the TxStartedConstants are found,
    else None

    NB - only specific treatments count - the generic (placeholders) such as
    "other" are not considered when looking up treatment start date.

    """
    cc_ids = set(cc.id for cc in TxStartedConstants())
    other_id = TxStartedConstants().OtherProcedure.id
    matching = [proc.start_time for proc in user.procedures
                if proc.code_id in cc_ids and proc.code_id != other_id]
    return max(matching) if matching else None


def known_treatment_not_started(user):
    """Returns True if the user has a procedure suggesting no Tx started

    If the user has a procedure suggesting treatment hasn't started, such as
    'Started watchful waiting', 'Started active surveillance' or
    'None of the Above', this will return True.

    A lack of information will return False, i.e. if user hasn't yet
    set any procedure information.

    """
    cc_ids = set(cc.id for cc in TxNotStartedConstants())
    has_procs = set(proc.code_id for proc in user.procedures)
    return not cc_ids.isdisjoint(has_procs)


class TxStartedConstants(object):
    """Attributes for known 'treatment started' codings

    Simple containment class with lazy loaded attributes for each
    codeable concept containing a known treatment started coding.

    NB - this also handles the bootstraping necessary to combine concepts
    from different coding systems under the same codeable_concept

    """
    __instance = None

    def __new__(cls):
        if TxStartedConstants.__instance is None:
            TxStartedConstants.__instance = object.__new__(cls)
        return TxStartedConstants.__instance

    def __iter__(self):
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            yield getattr(self, attr)

    @lazyprop
    def RadicalProstatectomy(self):
        sno = Coding(
            system=SNOMED, code='26294005',
            display='Radical prostatectomy (nerve-sparing)'
        ).add_if_not_found(True)
        ichom = Coding(
            system=ICHOM, code='3',
            display='Radical prostatectomy (nerve-sparing)'
        ).add_if_not_found(True)
        return CodeableConcept(
            codings=[sno, ichom], text='Radical prostatectomy (nerve-sparing'
        ).add_if_not_found(True)

    @lazyprop
    def RadicalProstatectomyNNS(self):
        sno = Coding(
            system=SNOMED, code='26294005-nns',
            display='Radical prostatectomy (non-nerve-sparing)'
        ).add_if_not_found(True)
        ichom = Coding(
            system=ICHOM, code='3-nns',
            display='Radical prostatectomy (non-nerve-sparing)'
        ).add_if_not_found(True)
        return CodeableConcept(
            codings=[sno, ichom],
            text='Radical prostatectomy (non-nerve-sparing'
        ).add_if_not_found(True)

    @lazyprop
    def ExternalBeamRadiationTherapy(self):
        sno = Coding(
            system=SNOMED, code='33195004',
            display='External beam radiation therapy'
        ).add_if_not_found(True)
        ichom = Coding(
            system=ICHOM, code='4',
            display='External beam radiation therapy'
        ).add_if_not_found(True)
        return CodeableConcept(
            codings=[sno, ichom],
            text='External beam radiation therapy').add_if_not_found(True)

    @lazyprop
    def Brachytherapy(self):
        sno = Coding(
            system=SNOMED, code='228748004', display='Brachytherapy'
        ).add_if_not_found(True)
        ichom = Coding(
            system=ICHOM, code='5',
            display='Brachytherapy').add_if_not_found(True)
        return CodeableConcept(
            codings=[sno, ichom],
            text='Brachytherapy').add_if_not_found(True)

    @lazyprop
    def AndrogenDeprivationTherapy(self):
        sno = Coding(
            system=SNOMED, code='707266006',
            display='Androgen deprivation therapy').add_if_not_found(True)
        ichom = Coding(
            system=ICHOM, code='6', display='Androgen deprivation therapy'
        ).add_if_not_found(True)
        return CodeableConcept(
            codings=[sno, ichom],
            text='Androgen deprivation therapy').add_if_not_found(True)

    @lazyprop
    def FocalTherapy(self):
        ichom = Coding(
            system=ICHOM, code='7', display='Focal therapy'
        ).add_if_not_found(True)
        return CodeableConcept(
            codings=[ichom], text='Focal therapy').add_if_not_found(True)

    @lazyprop
    def AndrogenDeprivationTherapySurgicalOrchiectomy(self):
        tnth = Coding(
            system=TRUENTH_CLINICAL_CODE_SYSTEM, code='androgen deprivation therapy - surgical orchiectomy',
            display='Androgen deprivation therapy (ADT) - Surgical orchiectomy').add_if_not_found(True)
        return CodeableConcept(codings=[tnth],
                               text='Androgen deprivation therapy (ADT) - Surgical orchiectomy').add_if_not_found(True)

    @lazyprop
    def AndrogenDeprivationTherapySurgicalChemical(self):
        tnth = Coding(
            system=TRUENTH_CLINICAL_CODE_SYSTEM, code='androgen deprivation therapy - chemical',
            display='Androgen deprivation therapy (ADT) - Chemical').add_if_not_found(True)
        return CodeableConcept(codings=[tnth],
                               text='Androgen deprivation therapy (ADT) - Chemical').add_if_not_found(True)

    @lazyprop
    def WholeGlandAblation(self):
        sno = Coding(
            system=SNOMED, code='176307007', display='Whole-gland ablation'
        ).add_if_not_found(True)
        return CodeableConcept(
            codings=[sno],
            text='Whole-gland ablation').add_if_not_found(True)

    @lazyprop
    def FocalGlandAblation(self):
        sno = Coding(
            system=SNOMED, code='438778003', display='Focal-gland ablation'
        ).add_if_not_found(True)
        return CodeableConcept(
            codings=[sno],
            text='Focal-gland ablation').add_if_not_found(True)

    @lazyprop
    def OtherProcedure(self):
        sno = Coding(
            system=SNOMED, code='118877007',
            display='Procedure on prostate').add_if_not_found(True)
        ichom = Coding(
            system=ICHOM, code='888', display='Other (free text)'
        ).add_if_not_found(True)
        return CodeableConcept(
            codings=[sno, ichom], text='Other procedure on prostate'
        ).add_if_not_found(True)

    @lazyprop
    def OtherPrimaryTreatment(self):
        sno = Coding(
            system=SNOMED, code='999999999', display='Other primary treatment'
        ).add_if_not_found(True)
        return CodeableConcept(
            codings=[sno],
            text='Other primary treatment').add_if_not_found(True)


class TxNotStartedConstants(object):
    """Attributes for known 'treatment not started' codings

    Simple containment class with lazy loaded attributes for each
    codeable concept containing a known procedure started coding.

    """
    __instance = None

    def __new__(cls):
        if TxNotStartedConstants.__instance is None:
            TxNotStartedConstants.__instance = object.__new__(cls)
        return TxNotStartedConstants.__instance

    def __iter__(self):
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            yield getattr(self, attr)

    @lazyprop
    def StartedWatchfulWaiting(self):
        sno = Coding(
            system=SNOMED, code='373818007',
            display='Started watchful waiting').add_if_not_found(True)
        ichom = Coding(
            system=ICHOM, code='1', display='Watchful waiting'
        ).add_if_not_found(True)
        return CodeableConcept(
            codings=[sno, ichom],
            text='Watchful waiting').add_if_not_found(True)

    @lazyprop
    def StartedActiveSurveillance(self):
        sno = Coding(
            system=SNOMED, code='424313000',
            display='Started active surveillance').add_if_not_found(True)
        ichom = Coding(
            system=ICHOM, code='2', display='Active surveillance'
        ).add_if_not_found(True)
        return CodeableConcept(
            codings=[sno, ichom],
            text='Active surveillance').add_if_not_found(True)

    @lazyprop
    def NoneOfTheAbove(self):
        tnth = Coding(
            system=TRUENTH_CLINICAL_CODE_SYSTEM, code='999',
            display='None').add_if_not_found(True)
        return CodeableConcept(codings=[tnth],
                               text='None').add_if_not_found(True)
