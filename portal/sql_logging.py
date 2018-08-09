"""Enhanced SQL Logging

This file is imported from factories/app.py but ONLY when LOG_SQL is set
in the configuration - as it's expensive and noisy to run

"""
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

from flask import current_app


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement,
                        parameters, context, executemany):
    # Store state in context for logging after cursor execute
    context._query_start_time = time.time()
    context._stmt = statement
    context._params = parameters


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement,
                        parameters, context, executemany):
    total = time.time() - context._query_start_time
    current_app.logger.debug(
        "Time: %.02fms Query: <%s> Parameters: <%s>" % (
            total*1000, context._stmt, context._params))


