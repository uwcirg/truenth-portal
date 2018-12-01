"""Module for i18n methods and functionality"""
from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402

import requests

POT_FILES = (
    'portal/translations/messages.pot',
    'portal/translations/js/src/frontend.pot',
)

class BearerAuth(requests.auth.AuthBase):
    def __init__(self, bearer_token):
        # setup any auth-related data here
        self.bearer_token = bearer_token

    def __call__(self, r):
        # modify and return the request
        r.headers['Authorization'] = 'Bearer {}'.format(self.bearer_token)
        return r
