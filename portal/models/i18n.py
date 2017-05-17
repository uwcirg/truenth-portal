"""Module for i18n methods and functionality"""
import sys
import os
from collections import defaultdict
from flask import current_app
from requests import post
from subprocess import check_call

from .app_text import AppText
from ..extensions import babel
from .intervention import Intervention
from .user import current_user


def get_db_strings():
    elements = defaultdict(set)
    for entry in AppText.query:
        if entry.custom_text:
            elements['"{}"'.format(entry.custom_text)].add("apptext: " + entry.name)
    for entry in Intervention.query:
        if entry.description:
            elements['"{}"'.format(entry.description)].add("interventions: " + entry.name)
        if entry.card_html:
            elements['"{}"'.format(entry.card_html)].add("interventions: " + entry.name)
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


def smartling_authenticate():
    url = 'https://api.smartling.com/auth-api/v2/authenticate'
    headers = {'Content-type': 'application/json'}
    data = {
        "userIdentifier": current_app.config.get("SMARTLING_USER_ID"),
        "userSecret": current_app.config.get("SMARTLING_USER_SECRET")
    }
    resp = post(url, json=data, headers=headers)
    if resp.status_code != 200:
        sys.exit("Could not connect to smartling!")
    resp_json = resp.json()
    if ('response' in resp_json) and ('data' in resp_json['response']):
        token = resp_json['response']['data'].get('accessToken')
    if not token:
        sys.exit("No access token found!")
    return token


def update_smartling(languages):
    # authenticate smartling
    auth = smartling_authenticate()
    # get relevant filepaths
    translation_fpath = os.path.join(current_app.root_path, "translations")
    pot_fpath = os.path.join(translation_fpath, 'messages.pot')
    config_fpath = os.path.join(current_app.root_path, "../instance/babel.cfg")
    # create new .pot file from code
    check_call(['pybabel', 'extract', '-F', config_fpath, '-o', pot_fpath,
                current_app.root_path])
    # update pot file with db values
    upsert_to_template_file()

    # create .po files from .pot file, upload to smartling
    for language in languages:
        po_fpath = os.path.join(translation_fpath, language,
                    "LC_MESSAGES/messages.po")
        if not os.path.exists(po_fpath):
            os.makedirs(os.path.join(translation_fpath,language,"LC_MESSAGES"))
        if os.path.isfile(po_fpath):
            cmd = ['pybabel', 'update', '-i', pot_fpath, '-d',
                    translation_fpath, '-l', language, '--no-wrap']
        else:
            cmd = ['pybabel', 'init', '-i', pot_fpath, '-d',
                    translation_fpath, '-l', language, '--no-wrap']
        check_call(cmd)

        filename = '{}_messages.po'.format(language)
        headers = {'Authorization': 'Bearer {}'.format(auth)}
        files = {'file': (filename, open(po_fpath, 'rb'))}
        data = {
            'fileUri': filename,
            'fileType': 'gettext'
        }
        resp = post('https://api.smartling.com/files-api/v2/projects/{}/' \
                'file'.format(current_app.config.get("SMARTLING_PROJECT_ID")),
                data=data, files=files, headers=headers)
        resp.raise_for_status()


@babel.localeselector
def get_locale():
    if current_user() and current_user().locale_code:
        return current_user().locale_code
    return current_app.config.get("DEFAULT_LOCALE")