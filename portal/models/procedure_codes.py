"""Module for pre defined procedure codes and shortcuts"""

from .fhir import codeable_concept_with_coding
from .lazy import lazyprop
from ..system_uri import SNOMED


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

    """

    def __iter__(self):
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            yield getattr(self, attr)

    @lazyprop
    def RadicalProstatectomy(self):
        return codeable_concept_with_coding(
            system=SNOMED, code='26294005',
            display='Radical prostatectomy (nerve-sparing)')

    @lazyprop
    def RadicalProstatectomyNNS(self):
        return codeable_concept_with_coding(
            system=SNOMED, code='26294005-nns',
            display='Radical prostatectomy (non-nerve-sparing)')

    @lazyprop
    def ExternalBeamRadiationTherapy(self):
        return codeable_concept_with_coding(
            system=SNOMED, code='33195004',
            display='External beam radiation therapy')

    @lazyprop
    def Brachytherapy(self):
        return codeable_concept_with_coding(
            system=SNOMED, code='228748004',
            display='Brachytherapy')

    @lazyprop
    def AndrogenDeprivationTherapy(self):
        return codeable_concept_with_coding(
            system=SNOMED, code='707266006',
            display='Androgen deprivation therapy')


class TxNotStartedConstants(object):
    """Attributes for known 'treatment not started' codings

    Simple containment class with lazy loaded attributes for each
    codeable concept containing a known procedure started coding.

    """

    def __iter__(self):
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            yield getattr(self, attr)

    @lazyprop
    def StartedWatchfulWaiting(self):
        return codeable_concept_with_coding(
            system=SNOMED, code='373818007',
            display='Started watchful waiting')

    @lazyprop
    def StartedActiveSurveillance(self):
        return codeable_concept_with_coding(
            system=SNOMED, code='424313000',
            display='Started active surveillance')

    @lazyprop
    def NoneOfTheAbove(self):
        return codeable_concept_with_coding(
            system=SNOMED, code='999999999',
            display='None of the above')


