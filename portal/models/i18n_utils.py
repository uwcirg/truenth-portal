"""Module for i18n methods and functionality"""
from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402


from collections import defaultdict
import io
import sys
import os
from zipfile import ZipFile

from flask import current_app
import requests
from polib import pofile

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
    # todo: close()/wrap with `with` as necessary
    fp = io.BytesIO(resp.content)
    return ZipFile(fp, "r")


def pos_from_zip(zipfile):
    """
    Extract PO files by locale from Smartling archive

    :param zipfile: open Smartling zip archive, each language in its own subdir
    """
    for po_uri in zipfile.namelist():
        locale_code = po_uri.split('/')[0].replace('-', '_')
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


def msgcat(*po_files):
    """Concatenate input po_files together, with later files overwriting earlier ones"""
    po_files = list(po_files)
    base_po = po_files.pop(0)
    current_app.logger.debug("Combining PO file with %d strings", len(base_po))
    for po_file in po_files:
        current_app.logger.debug("Combining PO file with %d strings", len(po_file))
        for entry in po_file:
            if base_po.find(entry.msgid):
                base_po.find(entry.msgid).msgstr = entry.msgstr
            else:
                base_po.append(entry)

    current_app.logger.debug("New PO file string count: %d", len(base_po))
    return base_po


def download_all_translations(state):
    """Download translations from all Smartling projects and combine"""
    creds = {'bearer_token': smartling_authenticate()}
    for pot_file_path in POT_FILES:
        dest_po_basename = os.path.basename(pot_file_path).split('.pot')[0]

        # list of per-project PO file objects, keyed by locale code
        po_files_to_merge = defaultdict(list)
        for project_id in current_app.config['SMARTLING_PROJECT_IDS']:
            current_app.logger.debug(
                "Downloading %s.pot translations from project %s",
                dest_po_basename,
                project_id,
            )
            all_locales_zipfile = download_zip_file(
                uri=pot_file_path,
                project_id=project_id,
                state=state,
                credentials=creds,
            )
            for po_locale_code, po in pos_from_zip(all_locales_zipfile):
                po_files_to_merge[po_locale_code].append(po)

        for locale_code, po_files in po_files_to_merge.items():
            current_app.logger.debug("Combining PO files")
            dest_po_path = os.path.join(
                current_app.root_path, "translations",
                locale_code, 'LC_MESSAGES',
            )
            dest_po = os.path.join(dest_po_path, '{}.po'.format(dest_po_basename))
            dest_mo = os.path.join(dest_po_path, '{}.mo'.format(dest_po_basename))

            combined_po = msgcat(*po_files)
            combined_po.save(dest_po)
            current_app.logger.info(
                "Saved combined PO file: %s",
                os.path.relpath(dest_po, current_app.root_path),
            )
            combined_po.save_as_mofile(dest_mo)
            current_app.logger.debug("Saved MO file %s", dest_mo)
