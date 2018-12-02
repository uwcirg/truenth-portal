"""Module for i18n methods and functionality"""
from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402

from io import BytesIO
from zipfile import ZipFile

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
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        sys.exit("Error authenticating with Smartling")

    try:
        token = resp.json()['response']['data']['accessToken']
    except KeyError:
        sys.exit("no smartling access token found")
    return token


def download_zip_file(credentials, project_id, uri, state):
    url = 'https://api.smartling.com/files-api/v2/projects/{}/locales/all/file/zip'.format(
        project_id
    )
    resp = requests.get(
        url,
        params={
            'retrievalType': state,
            'fileUri': uri,
        },
        auth=BearerAuth(**credentials),
    )
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        sys.exit("Error downloading file from Smartling")

    current_app.logger.debug("zip file downloaded from smartling")
    fp = BytesIO(resp.content)
    return ZipFile(fp, "r")
