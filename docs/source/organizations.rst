Organizations
*************

Organizations are used to name clinics and parent organizations.  Use
the `/api/organization` endpoint to view the list of organizations in the
system.

Add new organizations via **POST** to `/api/organization` with a JSON
document defining the organization compliant with the `FHIR Organization
<https://www.hl7.org/fhir/organization.html>`_ resource.

.. warning::

   The parent organization must exist in the system before a child
   can name it in the **partOf** reference.

To enable use of the `/go/<shortcut_alias>` endpoint, to pre-select
clinics for new users, an **identifier** must be included in the FHIR resource.

For example, after looking up the correct ID, a PUT of the following document
adds a shortcut alias to the *UCSF Urologic Surgical Oncology* organization.

.. note::

   For the shortcut alias to function, the added identifier must have
   a **system** value of `http://us.truenth.org/identity-codes/shortcut-alias`

PUT to /api/organization/6 ::

    $ cat data
    {
      "resourceType": "Organization",
      "identifier": [
          { "system": "http://us.truenth.org/identity-codes/shortcut-alias",
            "value": "ucsfurology"
          }
      ]
    }

    $ curl -H 'Authorization: Bearer <valid-token>' \
      -H 'Content-Type: application/json' -X PUT -d @data \
      https://stg.us.truenth.org/api/organization/6


Note that organizations now contain a set of 'options' fields, as follows:

- ``use_specific_codings`` : toggles whether or not the organization should use the subsequent custom options
- ``race_codings`` : toggles whether or not the organization should capture race information for its users
- ``ethnicity_codings`` : as above, but for ethnicity information
- ``indigenous_codings`` : as above, but for indigenous information

For each organization:

- If an org has a True value for ``use_specific_codings``, then the r/e/i properties will use the r/e/i options from that org
- If an org has False value for ``use_specific_codings``, and it has a parent, then the r/e/i properties will use the r/e/i options from the parent org. Note that this continues recursively, until either it hits either (a) an org with specific codings turned on, or (b) an org with no parent
- If an org has a False value for ``use_specific_codings``, and it has NO parent, then it will return true for all r/e/i properties.

These settings are accessible/set-able through the API (via any endpoint that uses the ``as_fhir`` or ``update_from_fhir`` methods)

For each user:

- There's a new property on the User model, ``org_coding_display_options``. If the user has any orgs, then this property will iterate through all the user's org. For each of the r/e/i options, if any of the orgs' r/e/i properties return true (using the logic presented above), then that user's r/e/i display setting will be set to true (otherwise, it's false).
- If the user has no orgs, these display settings default to true.

When displaying the user profile, each r/e/i section will check the relevant r/e/i display settings for the profile user, and use that to decide whether or not to display the relevant section.
