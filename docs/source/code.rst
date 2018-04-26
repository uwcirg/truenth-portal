Code Documentation
******************
All the project files contain some level of inline documentation.  Organized
below by module.

.. note::
    This does not include `API endpoints documented via swagger
    <https://stg.us.truenth.org/dist>`_, as the swagger syntax is
    incompatable with restructuredText

.. toctree::
    :maxdepth: 2

    portal
    portal_config
    portal_models
    portal_views

Open API/Swagger
================
API endpoints are documented inline, in the function docstring following the Open API (formerly Swagger) specification.

Examples
--------

Schema Reuse
^^^^^^^^^^^^

Open API schemas can be defined once and referenced by any other document. For example, the ``FHIRPatient`` ``schema`` defined in the body of one request ...::

    operationId: setPatientDemographics
    tags:
      - Demographics
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH patient ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: FHIRPatient
          required:
            - resourceType
          properties:
            resourceType:
              type: string
              description: defines FHIR resource type, must be Patient

... can be referenced in the body of the response::

    operationId: getPatientDemographics
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description:
          Optional TrueNTH patient ID, defaults to the authenticated user.
        required: true
        type: integer
        format: int64
    responses:
      200:
        description:
          Returns demographics for requested portal user id as a FHIR
          patient resource (http://www.hl7.org/fhir/patient.html) in JSON.
          Defaults to logged-in user if `patient_id` is not provided.
        schema:
          $ref: "#/definitions/FHIRPatient"
