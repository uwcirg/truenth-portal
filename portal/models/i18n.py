"""Module for i18n methods and functionality"""
import os
import re
import requests
import sys
import tempfile

from collections import defaultdict
from cStringIO import StringIO
from flask import current_app
from polib import pofile
from subprocess import check_call
from zipfile import ZipFile

from .app_text import AppText
from ..extensions import babel
from .intervention import Intervention
from .user import current_user


def get_db_strings():
    elements = defaultdict(set)
    for entry in AppText.query:
        if entry.custom_text:
            ct = re.sub('"', r'\\"', entry.custom_text)
            elements['"{}"'.format(ct)].add("apptext: " + entry.name)
    for entry in Intervention.query:
        if entry.description:
            desc = re.sub('"', r'\\"', entry.description)
            elements['"{}"'.format(desc)].add("interventions: " + entry.name)
        if entry.card_html:
            ch = re.sub('"', r'\\"', entry.card_html)
            elements['"{}"'.format(ch)].add("interventions: " + entry.name)
    return elements


def upsert_to_template_file():
    db_translatables = get_db_strings()
    if db_translatables:
        try:
            with open(os.path.join(current_app.root_path, "translations/messages.pot"),"r+") as potfile:
                potlines = potfile.readlines()
                for i, line in enumerate(potlines):
                    if line.split() and (line.split()[0] == "msgid"):
                        msgid = line.split(" ",1)[1].strip()
                        if msgid in db_translatables:
                            for location in db_translatables[msgid]:
                                locstring = "# " + location + "\n"
                                if not any(t == locstring for t in potlines[i-4:i]):
                                    potlines.insert(i,locstring)
                            del db_translatables[msgid]
                for entry, locations in db_translatables.items():
                    if entry:
                        for loc in locations:
                            potlines.append("# " + loc + "\n")
                        potlines.append("msgid " + entry + "\n")
                        potlines.append("msgstr \"\"\n")
                        potlines.append("\n")
                potfile.truncate(0)
                potfile.seek(0)
                potfile.writelines(potlines)
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            sys.exit("Could not write to translation file!\n ->%s" % (exceptionValue))


def fix_references(pot_fpath):
    """Fix reference comments to remove checkout-specific paths"""
    # Todo: override PoFileParser._process_comment() to perform this as part of `pybabel extract`

    path_regex = re.compile(r"^#: {}(?P<rel_path>.*):(?P<line>\d+)".format(
        os.path.dirname(current_app.root_path)
    ))
    base_url = "%s/tree/develop" % current_app.config.metadata.home_page

    with open(pot_fpath) as infile, tempfile.NamedTemporaryFile(
        prefix='fix_references_',
        suffix='.pot',
        delete=False,
    ) as tmpfile:
        for line in infile:
            tmpfile.write(path_regex.sub(r"#: %s\g<rel_path>#L\g<line>" % base_url, line))

    os.rename(tmpfile.name, pot_fpath)
    current_app.logger.debug("messages.pot file references fixed")

def smartling_authenticate():
    url = 'https://api.smartling.com/auth-api/v2/authenticate'
    headers = {'Content-type': 'application/json'}
    data = {
        "userIdentifier": current_app.config.get("SMARTLING_USER_ID"),
        "userSecret": current_app.config.get("SMARTLING_USER_SECRET")
    }
    resp = requests.post(url, json=data, headers=headers)
    if resp.status_code != 200:
        sys.exit("could not connect to smartling")
    resp_json = resp.json()
    if ('response' in resp_json) and ('data' in resp_json['response']):
        token = resp_json['response']['data'].get('accessToken')
    if not token:
        sys.exit("no smartling access token found")
    return token


def smartling_upload():
    # get relevant filepaths
    translation_fpath = os.path.join(current_app.root_path, "translations")
    messages_pot_fpath = os.path.join(translation_fpath, 'messages.pot')
    config_fpath = os.path.join(current_app.root_path, "../instance/babel.cfg")
    # create new .pot file from code
    check_call((
        'pybabel', 'extract',
        '--no-wrap',
        '--mapping-file', config_fpath,
        '--project', current_app.config.metadata.name,
        '--version', current_app.config.metadata.version,
        '--output-file', messages_pot_fpath,
        current_app.root_path,
    ))
    current_app.logger.debug("messages.pot file generated")
    # update .pot file with db values
    upsert_to_template_file()
    current_app.logger.debug("messages.pot file updated with db strings")

    fix_references(messages_pot_fpath)

    upload_pot_file(messages_pot_fpath, 'messages.pot',
                    'portal/translations/messages.pot')

    frontend_pot_fpath = os.path.join(translation_fpath, "js",
                                      "src", "frontend.pot")

    fix_references(frontend_pot_fpath)

    upload_pot_file(frontend_pot_fpath, 'frontend.pot',
                    'portal/translations/js/src/frontend.pot')


def upload_pot_file(fpath, fname, uri):
    project_id = current_app.config.get("SMARTLING_PROJECT_ID")
    if project_id and current_app.config.get("SMARTLING_USER_SECRET"):
        # authenticate smartling
        auth = smartling_authenticate()
        current_app.logger.debug("authenticated in smartling")
        # upload .pot file to smartling
        with open(fpath, 'rb') as potfile:
            headers = {'Authorization': 'Bearer {}'.format(auth)}
            files = {'file': (fname, potfile)}
            data = {
                'fileUri': uri,
                'fileType': 'gettext'
            }
            resp = requests.post('https://api.smartling.com'
                                 '/files-api/v2/projects/{}'
                                 '/file'.format(project_id),
                                 data=data, files=files, headers=headers)
            resp.raise_for_status()
        current_app.logger.debug(
            "{} uploaded to smartling project {}".format(fname, project_id)
        )
    else:
        current_app.logger.warn("missing smartling configuration - file {} "
                                "not uploaded".format(fname))


def smartling_download(language=None):
    translation_fpath = os.path.join(current_app.root_path, "translations")
    # authenticate smartling
    auth = smartling_authenticate()
    current_app.logger.debug("authenticated in smartling")
    # GET file(s) from smartling
    headers = {'Authorization': 'Bearer {}'.format(auth)}
    download_and_extract_po_file(language, 'messages', headers,
                                 'portal/translations/messages.pot')
    download_and_extract_po_file(language, 'frontend', headers,
                                 'portal/translations/js/src/frontend.pot')


def download_and_extract_po_file(language, fname, headers, uri):
    project_id = current_app.config.get("SMARTLING_PROJECT_ID")
    if language:
        response_content = download_po_file(language, headers,
                                            project_id, uri)
        extract_po_file(language, response_content, fname)
    else:
        zfp = download_zip_file(headers, project_id, uri)
        for langfile in zfp.namelist():
            langcode = re.sub('-','_',langfile.split('/')[0])
            data = zfp.read(langfile)
            if not data or not langcode:
                sys.exit('invalid po file for {}'.format(langcode))
            extract_po_file(langcode, data, fname)
    current_app.logger.debug(
            "{}.po files updated, mo files compiled".format(fname))


def download_po_file(language, headers, project_id, uri):
    if not re.match(r'[a-z]{2}_[A-Z]{2}', language):
        sys.exit('invalid language code; expected format xx_XX')
    language_id = re.sub('_', '-', language)
    url = 'https://api.smartling.com/files-api/v2/projects/' \
          '{}/locales/{}/file?fileUri={}'.format(project_id, language_id,
                                                 uri)
    resp = requests.get(url, headers=headers)
    if not resp.content:
        sys.exit('no file returned')
    current_app.logger.debug("{} po file downloaded "
                             "from smartling".format(language))
    return resp.content


def download_zip_file(headers, project_id, file_uri):
    url = 'https://api.smartling.com/files-api/v2/projects/' \
          '{}/locales/all/file/zip?fileUri={}&retrievalType=' \
          'published'.format(project_id, file_uri)
    resp = requests.get(url, headers=headers)
    if not resp.content:
        sys.exit('no file returned')
    current_app.logger.debug("zip file downloaded from smartling")
    fp = StringIO(resp.content)
    return ZipFile(fp, "r")


def extract_po_file(language, data, fname):
    po_path = os.path.join(current_app.root_path, "translations", language,
                           'LC_MESSAGES', 'temp_{}.po'.format(fname))
    with open(po_path, "wb") as fout:
        fout.write(data)
    current_app.logger.debug("{} po file extracted".format(language))
    merge_po_into_master(po_path, language, fname)
    os.remove(po_path)


def merge_po_into_master(po_path, language, fname):
    master_path = os.path.join(current_app.root_path, "translations",
                               language, 'LC_MESSAGES')
    mpo_path = os.path.join(master_path, '{}.po'.format(fname))
    incoming_po = pofile(po_path)
    if os.path.isfile(mpo_path):
        master_po = pofile(mpo_path)

        for entry in incoming_po:
            if master_po.find(entry.msgid):
                master_po.find(entry.msgid).msgstr = entry.msgstr
            else:
                master_po.append(entry)

        master_po.save(mpo_path)
        master_po.save_as_mofile(os.path.join(master_path, '{}.mo'.format(fname)))
    else:
        incoming_po.save(mpo_path)
        incoming_po.save_as_mofile(os.path.join(master_path, '{}.mo'.format(fname)))


@babel.localeselector
def get_locale():
    if current_user() and current_user().locale_code:
        return current_user().locale_code
    return current_app.config.get("DEFAULT_LOCALE")