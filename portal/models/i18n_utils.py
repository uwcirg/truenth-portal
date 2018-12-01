"""Module for i18n methods and functionality"""
from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402

from flask import current_app
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


def smartling_authenticate():
    resp = requests.post(
        url='https://api.smartling.com/auth-api/v2/authenticate',
        json={
            "userIdentifier": current_app.config["SMARTLING_USER_ID"],
            "userSecret": current_app.config["SMARTLING_USER_SECRET"],
        },
    )
    if resp.status_code != 200:
        sys.exit("could not connect to smartling")

    try:
        token = resp.json()['response']['data']['accessToken']
    except KeyError:
        sys.exit("no smartling access token found")
    return token
