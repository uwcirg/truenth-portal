Testing
*******

.. contents::
   :depth: 3
   :local:

Running Unit Tests
==================

See `Testing <readme_link.html#testing>`_ from the README


Debugging Views
===============

A number of endpoints can be used to view details of a patient, or manually
trigger an instant reminder, to simplify testing and debugging.

All of these endpoints are restricted by the same rules as any API, namely
the authenticated user must have appropriate permissions to make the request,
typically governed by user ROLE and shared organizations between the patient
and the current user.  A user can also view their own data in most cases.

For all of the following, replace the variable name within the angle brackets
with the appropriate value.

Communicate
-----------

Trigger an immediate lookup and transmission of any assessment reminder emails
for a user, rather than wait for the next scheduled job to handle.

Request ``/communicate/<patient_id>``

Additional query string parameters supported::

   trace=True
     Shows details of the lookup process
   purge=True
     invalidates the assessment_cache for the patient
     prior to executing the lookup

Assessment Status
-----------------

Request ``/api/patient/<patient_id>/assessment-status`` to view current
assessment status details::

   assessment_status
     The *overall* status for the patient's assessments.

   completed_ids
     A list of the named assessments for the current questionnaire bank which
     the patient has already submitted.

   outstanding_indefinite_work
     The ``irondemog`` or ``irondemog3`` assessment is special, belonging to
     the indefinite camp.  If the user is eligible and still needs to complete
     this assessment, this variable will be set to ``1``.

   qb_name
     The current Questionnaire Bank for the patient.

   questionnaires_ids
     The list of questionnaires the user needs to complete for the current
     Questionnaire Bank (specifically those which haven't been previously
     started and suspended).

   resume_ids
     The list of questionnaires the user has begun but not yet completed
     for the current Questionnaire Bank.

Additional query string parameters supported::

   trace=True
     Shows details of the lookup process

Invalidate Assessment Cache
---------------------------

Although many URLs listed in this document also support the ``purge=True``
parameter, it's also possible to invalidate the cached assessment status
of any given patient, which will then force a fresh lookup the next time
it is needed.

Request ``/api/invalidate/<patient_id>`` invalidates given user's cache,
and returns the patient data in FHIR format.
