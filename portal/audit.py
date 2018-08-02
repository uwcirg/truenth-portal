"""AUDIT module

Maintain a log exclusively used for recording auditable events.

Any action deemed an auditable event should make a call to
auditable_event()

Audit data is also persisted in the database *audit* table.

"""
from __future__ import unicode_literals  # isort:skip

import logging
import os
import sys

from flask import current_app

from .database import db
from .models.audit import Audit

# special log level for auditable events
# initial goal was to isolate all auditable events to one log handler
# revised to be a level less than ERROR, so auditable events aren't
# considered errors for error mail handling (see SMTPHandler)
AUDIT = int((logging.WARN + logging.ERROR) / 2)


def auditable_event(message, user_id, subject_id, context="other"):
    """Record auditable event

    message: The message to record, i.e. "log in via facebook"
    user_id: The authenticated user id performing the action
    subject_id: The user id upon which the action was performed

    """
    text = "performed by {0} on {1}: {2}: {3}".format(
        user_id, subject_id, context, message)
    current_app.logger.log(AUDIT, text)

    with db.session.no_autoflush:
        db.session.add(Audit(
            user_id=user_id, subject_id=subject_id, comment=message,
            context=context))
        db.session.commit()


def configure_audit_log(app):  # pragma: no cover
    """Configure audit logging.

    The audit log is only active when running as a service (not during
    database updates, etc.)  It should only received auditable events
    and never be rotated out.

    """
    # Skip config when running tests or maintenance
    if ((sys.argv[0].endswith('/bin/flask') and 'run' not in sys.argv) or
            app.testing):
        return

    logging.addLevelName('AUDIT', AUDIT)

    audit_log_handler = logging.StreamHandler(sys.stdout)
    if app.config.get('LOG_FOLDER', None):
        audit_log = os.path.join(app.config['LOG_FOLDER'], 'audit.log')
        audit_log_handler = logging.FileHandler(audit_log, delay=True)

    audit_log_handler.setLevel(AUDIT)
    audit_log_handler.setFormatter(
        logging.Formatter('%(asctime)s: %(message)s'))
    app.logger.addHandler(audit_log_handler)
