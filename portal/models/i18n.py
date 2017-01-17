"""Module for i18n methods and functionality"""
import psycopg2
import sys
import os
from flask import current_app
from ..extensions import babel
from .user import current_user


def parse_connection_uri():
    here, _ = os.path.split(__file__)
    with open(os.path.join(current_app.root_path, '../instance/application.cfg'), 'r') as fh:
        conn_strings = [l for l in fh.readlines() if
                        l.startswith('SQLALCHEMY_DATABASE_URI')]

    if len(conn_strings) != 1:
        raise ValueError("can't find connection string in application.cfg")
    conn_uri = conn_strings[0].split('=')[1]
    return conn_uri.strip()[1:-1]  # strip quotes, newlines


def connect_to_db():
    try:
        connection_uri = parse_connection_uri()
        conn = psycopg2.connect(connection_uri)
        return conn.cursor()
    except:
        exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
        sys.exit("Database connection failed!\n ->%s" % (exceptionValue))


def add_to_dict(d,k,o):
    if k:
        key = "\"" + k + "\""
        if key not in d:
            d[key] = set()
        d[key].add(o)


def get_db_strings():
    cur = connect_to_db()
    if cur:
        elements = {}
        cur.execute("""SELECT custom_text, name FROM apptext""")
        for entry in cur.fetchall():
            add_to_dict(elements,entry[0],"apptext: " + entry[1])
        cur.execute("""SELECT description, name FROM interventions""")
        for entry in cur.fetchall():
            add_to_dict(elements,entry[0],"interventions: " + entry[1])
        cur.execute("""SELECT card_html, name FROM interventions""")
        for entry in cur.fetchall():
            add_to_dict(elements,entry[0],"interventions: " + entry[1])
        return elements


def upsert_to_template_file():
    db_translatables = get_db_strings()
    if db_translatables:
        # try:
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
        # except:
        #     exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
        #     sys.exit("Could not write to translation file!\n ->%s" % (exceptionValue))


@babel.localeselector
def get_locale():
    if current_user() and current_user().locale_code:
        return current_user().locale_code
    return current_app.config.get("DEFAULT_LOCALE")