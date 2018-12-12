from enum import Enum


class OverallStatus(Enum):
    """ Overall assessment status for a given (QB, user)

    'Completed': if all questionnaires in the bank were completed.
    'Due': if all questionnaires are un-started and the days since
        consenting hasn't exceeded the 'days_till_due' for all
        questionnaires.
    'Expired': if we don't have a consent date for the user, or
        if there are no questionnaires assigned to the user, or
        if all questionnaires in the bank have expired.
    'Overdue': if all questionnaires are un-started and the days since
        consenting hasn't exceeded the 'days_till_overdue' for all
        questionnaires.  (NB - check for 'due' runs first)
    'Partially Completed': if one or more questionnaires were at least
        started and at least one questionnaire is expired.
    'In Progress': if one or more questionnaires were at least
        started and the remaining unfinished questionnaires are not
        expired.
    'Withdrawn': if the user's latest consent agreement with QB
        organization has status == "suspended".

    """
    (completed, due, expired, overdue, partially_completed, in_progress,
     withdrawn) = range(7)

    def __str__(self):
        """Custom string representation to present pretty title case

        For example:
         "status {}".format(OverallStatus.in_progress) generates
         "status In Progress"

        """
        s = self.name.replace('_', ' ')
        return s.title()
