from .coding import Coding
from .lazy import lazyprop
from ..system_uri import IETF_LANGUAGE_TAG


class LocaleConstants(object):
    """Attributes for built in locales

    Additions may be defined in persistence files, base values defined
    within for easy access and testing

    """

    def __iter__(self):
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            yield getattr(self, attr)

    @lazyprop
    def AmericanEnglish(self):
        Coding(
            system=IETF_LANGUAGE_TAG, code='en_US',
            display='American English').add_if_not_found(True)

    @lazyprop
    def AustralianEnglish(self):
        Coding(
            system=IETF_LANGUAGE_TAG, code='en_AU',
            display='Australian English').add_if_not_found(True)
