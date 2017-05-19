"""Module for i18n methods and functionality"""
import sys
import os
import re
import requests
from collections import defaultdict
from cStringIO import StringIO
from flask import current_app
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
    # authenticate smartling
    auth = smartling_authenticate()
    current_app.logger.debug("authenticated in smartling")
    # get relevant filepaths
    translation_fpath = os.path.join(current_app.root_path, "translations")
    pot_fpath = os.path.join(translation_fpath, 'messages.pot')
    config_fpath = os.path.join(current_app.root_path, "../instance/babel.cfg")
    # create new .pot file from code
    check_call(['pybabel', 'extract', '-F', config_fpath, '-o', pot_fpath,
                current_app.root_path])
    current_app.logger.debug("messages.pot file generated")
    # update .pot file with db values
    upsert_to_template_file()
    current_app.logger.debug("messages.pot file updated with db strings")
    # upload .pot file to smartling
    with open(pot_fpath, 'rb') as potfile:
        headers = {'Authorization': 'Bearer {}'.format(auth)}
        files = {'file': ('messages.pot', potfile)}
        data = {
            'fileUri': 'portal/translations/messages.pot',
            'fileType': 'gettext'
        }
        resp = requests.post('https://api.smartling.com' \
                '/files-api/v2/projects/{}/' \
                'file'.format(current_app.config.get("SMARTLING_PROJECT_ID")),
                data=data, files=files, headers=headers)
        resp.raise_for_status()
    current_app.logger.debug("messages.pot uploaded to smartling")


def smartling_download(language=None):
    translation_fpath = os.path.join(current_app.root_path, "translations")
    # authenticate smartling
    auth = smartling_authenticate()
    current_app.logger.debug("authenticated in smartling")
    # GET file(s) from smartling
    headers = {'Authorization': 'Bearer {}'.format(auth)}
    if language:
        if not re.match(r'[a-z]{2}_[A-Z]{2}',language):
            sys.exit('invalid language code; expected format xx_XX')
        language_id = re.sub('_','-',language)
        url = 'https://api.smartling.com/files-api/v2/projects/' \
            '{}/locales/{}/file?fileUri={}'.format(
                current_app.config.get("SMARTLING_PROJECT_ID"), language_id,
                'portal/translations/messages.pot')
        resp = requests.get(url, headers=headers)
        if not resp.content:
            sys.exit('no file returned')
        current_app.logger.debug("{} po file downloaded " \
                                "from smartling".format(language))
        po_path = os.path.join(translation_fpath, language,
                                'LC_MESSAGES', 'messages.po')
        with open(po_path,"wb") as fout:
            fout.write(resp.content)
        current_app.logger.debug("{} po file saved".format(language))
    else:
        url = 'https://api.smartling.com/files-api/v2/projects/' \
            '{}/locales/all/file/zip?fileUri={}&retrievalType=' \
            'published'.format(current_app.config.get("SMARTLING_PROJECT_ID"),
                'portal/translations/messages.pot')
        resp = requests.get(url, headers=headers)
        if not resp.content:
            sys.exit('no file returned')
        current_app.logger.debug("zip file downloaded from smartling")
        fp = StringIO(resp.content)
        zfp = ZipFile(fp, "r")
        for langfile in zfp.namelist():
            langcode = re.sub('-','_',langfile.split('/')[0])
            po_path = os.path.join(translation_fpath, langcode,
                                'LC_MESSAGES', 'messages.po')
            data = zfp.read(langfile)
            if not data or not langcode:
                sys.exit('invalid po file for {}'.format(langcode))
            with open(po_path,"wb") as fout:
                fout.write(data)
            current_app.logger.debug("{} po file saved".format(langcode))
    # compile .mo file(s) from .po file(s)
    check_call(['pybabel','compile','-f','-d',translation_fpath])
    current_app.logger.debug("babel mo files compiled and updated")


@babel.localeselector
def get_locale():
    if current_user() and current_user().locale_code:
        return current_user().locale_code
    return current_app.config.get("DEFAULT_LOCALE")