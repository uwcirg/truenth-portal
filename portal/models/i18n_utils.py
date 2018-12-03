"""Module for i18n methods and functionality"""
from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402

import io
import sys
from zipfile import ZipFile

from flask import current_app
import requests

POT_FILES = (
    'portal/translations/messages.pot',
    'portal/translations/js/src/frontend.pot',
)


class BearerAuth(requests.auth.AuthBase):
    """Add bearer token to HTTP headers for authenticated requests to Smartling"""
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
    fp = io.BytesIO(resp.content)
    return ZipFile(fp, "r")


def pos_from_zip(zipfile):
    """Extract PO files by locale from Smartling archive"""
    for po_uri in zipfile.namelist():
        locale_code = po_uri.split('/')[0].replace('-','_')
        content = zipfile.read(po_uri).decode("utf8")

        try:
            po = pofile(content)
        except IOError as e:
            current_app.logger.error(e)

            bad_po = '/tmp/{}-bad.po'.format(locale_code)
            with io.open(bad_po, 'w', encoding='utf8') as out_po:
                out_po.write(content)
            sys.exit("Error in extracted PO file ({}); wrote to {}".format(po_uri, bad_po))
        yield locale_code, po

