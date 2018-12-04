"""Module for i18n methods and functionality"""
from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402

from collections import defaultdict
from io import BytesIO
import os
import re
from subprocess import check_call
import sys
import tempfile

from babel import negotiate_locale
from flask import current_app, has_request_context, request, session
from polib import pofile
import requests

from ..extensions import babel
from ..system_uri import IETF_LANGUAGE_TAG
from .app_text import AppText
from .coding import Coding
from .i18n_utils import BearerAuth, download_zip_file, smartling_authenticate
from .intervention import Intervention
from .organization import Organization
from .questionnaire_bank import QuestionnaireBank, classification_types_enum
from .research_protocol import ResearchProtocol
from .role import Role
from .user import current_user


def get_db_strings():
    msgid_map = defaultdict(set)
    i18n_fields = {
        AppText: ('custom_text',),
        Intervention: ('description', 'card_html'),
        Organization: ('name',),
        QuestionnaireBank: ('display_name',),
        ResearchProtocol: ('display_name',),
        Role: ('display_name',)
    }

    for model, fields in i18n_fields.items():
        for entry in model.query:
            for field_name in fields:
                msgid = getattr(entry, field_name)
                if not msgid:
                    continue
                msgid = '"{}"'.format(re.sub('"', r'\\"', msgid))
                msgid_map[msgid].add("{model_name}: {field_ref}".format(
                    model_name=model.__name__,
                    field_ref=entry.name,
                ))
    return msgid_map


def get_static_strings():
    """Manually add strings that are otherwise difficult to extract"""
    msgid_map = {}
    status_strings = (
        'Completed',
        'Due',
        'In Progress',
        'Overdue',
        'Expired',
    )
    msgid_map.update({
        '"{}"'.format(s):
            {'assessment_status: %s' % s} for s in status_strings
    })

    enum_options = {
        classification_types_enum: ('title',),
    }
    for enum, options in enum_options.items():
        for value in enum.enums:
            for function_name in options:
                value = getattr(value, function_name)()
            msgid_map['"{}"'.format(value)] = {'{}: {}'.format(
                enum.name, value)}
    return msgid_map


def upsert_to_template_file():
    db_translatables = {}
    db_translatables.update(get_db_strings())
    if not db_translatables:
        current_app.logger.warn("no DB strings extracted")
        return

    db_translatables.update(get_static_strings())

    try:
        with open(
            os.path.join(
                current_app.root_path,
                "translations/messages.pot",
            ),
            "r+",
        ) as potfile:
            potlines = potfile.readlines()
            for i, line in enumerate(potlines):
                if not line.split() or (line.split()[0] != "msgid"):
                    continue
                msgid = line.split(" ", 1)[1].strip()
                if msgid not in db_translatables:
                    continue
                for location in db_translatables[msgid]:
                    locstring = "# " + location + "\n"
                    if not any(t == locstring for t in potlines[i - 4:i]):
                        potlines.insert(i, locstring)
                del db_translatables[msgid]
            for entry, locations in db_translatables.items():
                if not entry:
                    continue
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
        sys.exit(
            "Could not write to translation file!\n ->%s" % (exceptionValue))


def fix_references(pot_fpath):
    """Fix reference comments to remove checkout-specific paths"""
    # Todo: override PoFileParser._process_comment() to perform this as part of `pybabel extract`

    path_regex = re.compile(r"^#: {}(?P<rel_path>.*):(?P<line>\d+)".format(
        os.path.dirname(current_app.root_path)
    ))
    base_url = "%s/tree/develop" % current_app.config.metadata['home-page']

    with open(pot_fpath) as infile, tempfile.NamedTemporaryFile(
        prefix='fix_references_',
        suffix='.pot',
        delete=False,
    ) as tmpfile:
        for line in infile:
            tmpfile.write(
                path_regex.sub(r"#: %s\g<rel_path>#L\g<line>" % base_url,
                               line))

    os.rename(tmpfile.name, pot_fpath)
    current_app.logger.debug("messages.pot file references fixed")


def smartling_upload():
    # get relevant filepaths
    config_fname = current_app.config['BABEL_CONFIG_FILENAME']
    translation_fpath = os.path.join(current_app.root_path, "translations")
    messages_pot_fpath = os.path.join(translation_fpath, 'messages.pot')
    config_fpath = os.path.join(
        current_app.root_path, "../instance/", config_fname
    )

    # create new .pot file from code
    check_call((
        'pybabel', 'extract',
        '--no-wrap',
        '--mapping-file', config_fpath,
        '--project', current_app.config.metadata['name'],
        '--version', current_app.config.metadata['version'],
        '--output-file', messages_pot_fpath,
        current_app.root_path,
    ))
    current_app.logger.debug("messages.pot file generated")

    # update .pot file with db values
    upsert_to_template_file()
    current_app.logger.debug("messages.pot file updated with db strings")

    fix_references(messages_pot_fpath)
    upload_pot_file(
        fpath=messages_pot_fpath,
        fname='messages.pot',
        uri='portal/translations/messages.pot',
    )

    frontend_pot_fpath = os.path.join(
        translation_fpath, "js", "src", "frontend.pot"
    )

    fix_references(frontend_pot_fpath)
    upload_pot_file(
        fpath=frontend_pot_fpath,
        fname='frontend.pot',
        uri='portal/translations/js/src/frontend.pot'
    )


def upload_pot_file(fpath, fname, uri):
    upload_url = 'https://api.smartling.com/files-api/v2/projects/{}/file'
    project_id = current_app.config.get("SMARTLING_PROJECT_ID")
    if project_id and current_app.config.get("SMARTLING_USER_SECRET"):
        creds = {'bearer_token': smartling_authenticate()}
        current_app.logger.debug("authenticated in smartling")
        with open(fpath, 'rb') as potfile:
            resp = requests.post(
                upload_url.format(project_id),
                data={'fileUri': uri, 'fileType': 'gettext'},
                files={'file': (fname, potfile)},
                auth=BearerAuth(**creds)
            )
            resp.raise_for_status()
        current_app.logger.debug(
            "{} uploaded to smartling project {}".format(fname, project_id)
        )
    else:
        current_app.logger.warn(
            "missing smartling config - file {} not uploaded".format(fname)
        )


def smartling_download(state, language=None):
    project_id = current_app.config.get("SMARTLING_PROJECT_ID")

    creds = {'bearer_token': smartling_authenticate()}
    current_app.logger.debug("authenticated in smartling")
    download_and_extract_po_file(
        language=language,
        fname='messages',
        uri='portal/translations/messages.pot',
        state=state,
        credentials=creds,
        project_id=project_id,
    )
    download_and_extract_po_file(
        language=language,
        fname='frontend',
        uri='portal/translations/js/src/frontend.pot',
        state=state,
        credentials=creds,
        project_id=project_id,
    )


def download_and_extract_po_file(language, fname, credentials, uri, state, project_id):
    if language:
        response_content = download_po_file(
            language=language,
            project_id=project_id,
            uri=uri,
            state=state,
            credentials=credentials,
        )
        write_po_file(language, response_content, fname)
    else:
        zfp = download_zip_file(
            uri=uri,
            project_id=project_id,
            state=state,
            credentials=credentials,
        )
        for langfile in zfp.namelist():
            langcode = langfile.split('/')[0].replace('-', '_')
            po_data = zfp.read(langfile)
            if not po_data or not langcode:
                sys.exit('invalid po file for {}'.format(langcode))
            write_po_file(langcode, po_data, fname)
    current_app.logger.debug(
        "{}.po files updated, mo files compiled".format(fname))


def download_po_file(language, credentials, project_id, uri, state):
    if not re.match(r'[a-z]{2}_[A-Z]{2}', language):
        sys.exit('invalid language code; expected format xx_XX')
    language_id = re.sub('_', '-', language)
    url = 'https://api.smartling.com/files-api/v2/projects/{}/locales/{}/file'.format(
        project_id,
        language_id,
    )
    resp = requests.get(
        url,
        auth=BearerAuth(**credentials),
        params={
            'retrievalType': state,
            'fileUri': uri,
        },
    )
    if not resp.content:
        sys.exit('no file returned')
    current_app.logger.debug("{} po file downloaded "
                             "from smartling".format(language))
    return resp.content


def write_po_file(language, po_data, fname):
    po_dir = os.path.join(
        current_app.root_path,
        "translations",
        language,
        'LC_MESSAGES',
        'temp_{}.po'.format(fname),
    )
    temp_po_path = os.path.join(po_dir, 'temp_{}.po'.format(fname))

    # Create directory if necessary
    try:
        os.makedirs(po_dir)
    except OSError:
        if not os.path.isdir(po_dir):
            raise

    with open(temp_po_path, "wb") as fout:
        fout.write(po_data)
    current_app.logger.debug("{} po file extracted".format(language))
    merge_po_into_master(temp_po_path, language, fname)
    os.remove(temp_po_path)


def merge_po_into_master(input_po_path, language, dest_po_basename):
    """
    Merge PO file into corresponding per-language PO file

    :param input_po_path: input (temp) PO file to merge
    :param language: language to operate on
    :param dest_po_basename: destination file basename (without extension) in translations/
    """
    master_path = os.path.join(
        current_app.root_path, "translations", language, 'LC_MESSAGES',
    )

    mpo_path = os.path.join(master_path, '{}.po'.format(dest_po_basename))
    incoming_po = pofile(input_po_path)
    if os.path.isfile(mpo_path):
        master_po = pofile(mpo_path)

        for entry in incoming_po:
            if master_po.find(entry.msgid):
                master_po.find(entry.msgid).msgstr = entry.msgstr
            else:
                master_po.append(entry)

        master_po.save(mpo_path)
        master_po.save_as_mofile(
            os.path.join(master_path, '{}.mo'.format(dest_po_basename)))
        current_app.logger.debug(
            "merged {s_file} into {d_file}".format(
                s_file=os.path.relpath(incoming_po.fpath, current_app.root_path),
                d_file=os.path.relpath(master_po.fpath, current_app.root_path),
            )
        )
    else:
        incoming_po.save(mpo_path)
        incoming_po.save_as_mofile(
            os.path.join(master_path, '{}.mo'.format(dest_po_basename)))
        current_app.logger.debug('no existing file; saved {}'.format(mpo_path))


@babel.localeselector
def get_locale():
    if current_user() and current_user().locale_code:
        return current_user().locale_code

    # look for session variable in pre-logged-in state
    # confirm request context - not available from celery tasks
    if has_request_context():
        if session.get('locale_code'):
            return session['locale_code']
        browser_pref = negotiate_locale(
            preferred=(
                l.replace('-', '_') for l in request.accept_languages.values()
            ),
            available=(
                c.code for c in Coding.query.filter_by(system=IETF_LANGUAGE_TAG)
            ),
        )
        if browser_pref:
            return browser_pref
    return current_app.config.get("DEFAULT_LOCALE")
