#!/usr/bin/python
import psycopg2
import sys
import os

def parse_connection_uri():
    here, _ = os.path.split(__file__)
    with open(os.path.join(here, '../portal/application.cfg'), 'r') as fh:
        conn_strings = [l for l in fh.readlines() if
                        l.startswith('SQLALCHEMY_DATABASE_URI')]

    if len(conn_strings) != 1:
        raise ValueError("can't find connection string in application.cfg")
    conn_uri = conn_strings[0].split('=')[1]
    return conn_uri.strip()[1:-1]  # strip quotes, newlines

connection_uri = parse_connection_uri()
print "Connecting to database\n ->{}".format(connection_uri)

try:
    conn = psycopg2.connect(connection_uri)
    cursor = conn.cursor()
    print "Connected!\n"
except:
    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
    sys.exit("Database connection failed!\n ->%s" % (exceptionValue))
