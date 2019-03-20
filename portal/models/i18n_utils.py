"""Module for i18n methods and functionality"""
from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402


from collections import defaultdict
import io
import os
import sys
from zipfile import ZipFile

from flask import current_app
from polib import pofile, POFile
import requests

from .i18n import get_db_strings, get_static_strings

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


def download_zip_file(credentials, project_id, uri, state, include_origs='false'):
    """Download an archive of all translations for a given fileUri

    :param credentials: credentials necessary for authentication
    :type credentials: dict
    :param project_id: Smartling project id
    :param uri: Smartling fileUri, a path relative to portal/
    :param state: state of translations to download (eg published, in-progress)
    :param include_origs: when the translation is missing,
        whether or not to include the original string as the translation in PO files
        ie copy msgid as msgstr
        See https://help.smartling.com/hc/en-us/articles/360008000733-JSON#return-untranslated-strings-as-empty
    :returns: zip file content
    :rtype: bytestring
    """
    url = 'https://api.smartling.com/files-api/v2/projects/{}/locales/all/file/zip'.format(
        project_id
    )
    resp = requests.get(
        url,
        params={
            'includeOriginalStrings': include_origs,
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
    return resp.content


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
        zip_contents = download_zip_file(
            uri=uri,
            project_id=project_id,
            state=state,
            credentials=credentials,
        )
        with io.BytesIO(zip_contents) as zip_fp, ZipFile(zip_fp, "r") as zfp:
            for langfile in zfp.namelist():
                langcode = langfile.split('/')[0].replace('-', '_')
                po_data = zfp.read(langfile)
                if not po_data or not langcode:
                    sys.exit('invalid po file for {}'.format(langcode))
                write_po_file(langcode, po_data, fname)
    current_app.logger.debug(
        "{}.po files updated, mo files compiled".format(fname))


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


def msgcat(*po_files, **kwargs):
    """Concatenate input po_files together, with later files overwriting earlier ones"""
    po_files = list(po_files)

    # use given base_po, or empty PO file
    base_po = kwargs.get('base_po', POFile())
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
            zip_contents = download_zip_file(
                uri=pot_file_path,
                project_id=project_id,
                state=state,
                credentials=creds,
            )
            with io.BytesIO(zip_contents) as zip_fp, ZipFile(zip_fp, "r") as locales_zip:
                for po_locale_code, po in pos_from_zip(locales_zip):
                    po_files_to_merge[po_locale_code].append(po)

        for locale_code, po_files in po_files_to_merge.items():
            current_app.logger.debug(
                "Combining PO files for %s.pot (%s)",
                dest_po_basename,
                locale_code,
            )
            dest_po_path = os.path.join(
                current_app.root_path, "translations",
                locale_code, 'LC_MESSAGES',
            )
            dest_po = os.path.join(dest_po_path, '{}.po'.format(dest_po_basename))
            dest_mo = os.path.join(dest_po_path, '{}.mo'.format(dest_po_basename))

            # disable line-wrapping
            base_po = POFile(wrapwidth=-1)

            # re-use metadata of first PO file
            # todo: set config common for pybabel extract too
            base_po.metadata = po_files[0].metadata
            combined_po = msgcat(*po_files, base_po=base_po)

            # Create directory if necessary
            if not os.path.isdir(dest_po_path):
                try:
                    os.makedirs(dest_po_path)
                except OSError as e:
                    current_app.logger.error(e)
                    sys.exit("Error in creating directory {}".format(os.path.dirname(dest_po_path)))

            combined_po.save(dest_po)
            current_app.logger.info(
                "Saved combined PO file: %s",
                os.path.relpath(dest_po, current_app.root_path),
            )

            combined_po.save_as_mofile(dest_mo)
            current_app.logger.info(
                "Saved combined MO file: %s",
                os.path.relpath(dest_mo, current_app.root_path),
            )


def compile_pos():
    """Compile all back-end PO files to MO files"""

    translations_dir = os.path.join(current_app.root_path, "translations")
    for dirpath, _, filenames in os.walk(translations_dir):
        # only act on backend (flask) translation files
        if 'messages.po' not in filenames:
            continue

        po_filepath = os.path.join(dirpath, 'messages.po')
        mo_filepath = os.path.join(dirpath, 'messages.mo')

        pofile(po_filepath).save_as_mofile(mo_filepath)
        current_app.logger.debug(
            "Saved MO file: %s",
            os.path.relpath(mo_filepath, current_app.root_path),
        )


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


def download_po_file(language, credentials, project_id, uri, state):
    if not re.match(r'[a-z]{2}_[A-Z]{2}', language):
        sys.exit('invalid language code; expected format xx_XX')
    language_id = language.replace('_', '-')
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
