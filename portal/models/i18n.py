"""Module for i18n methods and functionality"""
import sys
import os
from collections import defaultdict
from flask import current_app
from ..extensions import babel
from .user import current_user
from .app_text import AppText
from .intervention import Intervention


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


@babel.localeselector
def get_locale():
    if current_user() and current_user().locale_code:
        return current_user().locale_code
    return current_app.config.get("DEFAULT_LOCALE")