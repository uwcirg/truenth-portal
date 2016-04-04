"""AUDIT module

Maintain a log exclusively used for recording auditable events.

Any action deemed an auditable event should make a call to
auditable_event()

"""
import os
import sys
import logging
from flask import current_app

# special log level for auditable events
# initial goal was to isolate all auditable events to one log handler
# revised to be a level less than ERROR, so auditable events aren't
# considered errors for error mail handling (see SMTPHandler)
AUDIT = (logging.WARN + logging.ERROR) / 2


def auditable_event(message, user_id, other_user_id=None):
    """Record auditable event

    message: The message to record, i.e. "log in via facebook"
    user_id: The authenticated user id performing the action
    other_user_id: Optional for events performed on user other than
                   authenticated
    """
    if other_user_id:
        text = "{0} performed on user {1}: {2}".format(user_id, other_user_id,
                                                       message)
    else:
        text = "{0} performed: {1}".format(user_id, message)
    current_app.logger.log(AUDIT, text)


def configure_audit_log(app):
    """Configure audit logging.

    The audit log is only active when running as a service (not during
    database updates, etc.)  It should only received auditable events
    and never be rotated out.

    """
    # Skip config when running tests or maintenance
    if ('manage.py' in sys.argv and 'runserver' not in sys.argv) or\
       app.testing:
        return

    logging.addLevelName('AUDIT', AUDIT)
    audit_log = os.path.join(app.config['LOG_FOLDER'], 'audit.log')
    audit_file_handler = logging.FileHandler(audit_log, delay=True)
    audit_file_handler.setLevel(AUDIT)
    audit_file_handler.setFormatter(
        logging.Formatter('%(asctime)s: %(message)s'))
    app.logger.addHandler(audit_file_handler)
