Interventions
*************

.. contents::
   :depth: 3
   :local:

Roles
=====

Any client can assume the role of an intervention.  By doing so, the client
becomes the **official** implementation for said role.

Access
======

Controlling access to interventions deserves special mention.  On the
``/client/<client_id>`` page, the application developer may view and
alter the value of **public_accessible**.

.. note::

   With **public_accessible** set, the intervention will always be displayed.

When **public_accessible** is *not* set, two additional options exist for
enabling said intervention.

    1. To control per user, the service account associated with the intervention
    should make use of the ``/api/intervention/<intervention_name>/`` `endpoint
    <https://stg.us.truenth.org/dist/#!/Intervention/user_intervention_set>`__.

    2. Alternatively, any number of *strategy* functions can be added to an
    intervention, to give access to any subgroup of users as defined by the
    strategy itself.  The available strategies are defined in the
    ``portal.models.intervention_strategies`` module, such as the `allow_if_not_in_intervention
    <portal_models.html#portal.models.intervention_strategies.allow_if_not_in_intervention>`_
    strategy.  Use the
    ``/api/intervention/<intervention_name>/access_rule`` `endpoint
    <portal_views.html#portal.views.intervention.intervention_rule_set>`__ to view or modify.

.. note::

   All of the checks above function as a short-circuited **or**.  That is,
   the first check that evaluates as True grants the user access to the
   intervention. See combine_strategies_ for a workaround.

.. note::

   An optional **rank** setting (unique integer value sorted in ascending
   order) may be included to control the order of evaluation when multiple
   strategies are in use.  Strategies with a rank value will be evaluated
   before those without a set rank.

For example, to add a rule that enables the *care_plan* intervention for
users registered with the `UCSF` clinic::

    $ cat data
    {"name": "UCSF Patients",
     "function_details": {
       "function": "limit_by_clinic_list",
       "kwargs': [{"name": "org_list",
                 "value": ["UCSF",]},]
      }
    }

    $ curl -H 'Authorization: Bearer <valid-token>' \
      -H 'Content-Type: application/json' -X POST -d @data \
      https://stg.us.truenth.org/api/intervention/care_plan/access_rule

.. _combine_strategies:

Sometimes it is necessary to combine multiple strategies into a logical
**AND** operation.  To do so, use the ``combine_strategies`` function,
passing the respective set of `strategy_n` and `strategy_n_kwargs` as so::

    {
      "name": "not in sr AND in clinc uw",
      "function_details": {
        "function": "combine_strategies",
        "name": "not in sr AND in clinc uw",
        "kwargs": [{
          "name": "strategy_1",
          "value": "allow_if_not_in_intervention"
        }, {
          "name": "strategy_1_kwargs",
          "value": [{
            "name": "intervention_name",
            "value": "sexual_recovery"
          }]
        }, {
          "name": "strategy_2",
          "value": "limit_by_clinic_list"
        }, {
          "name": "strategy_2_kwargs",
          "value": [{
            "name": "org_list",
            "value": ["UW Medicine (University of Washington)",]
          }]
        }]
      }
    }

The full list of strategies used for DECISION_SUPPORT_P3P::

    {
      "name": "P3P Access Conditions", 
      "description": "[strategy_1: (user NOT IN sexual_recovery)] AND [strategy_2 <a nested combined strategy>: ((user NOT IN list of clinics (including UCSF)) OR (user IN list of clinics including UCSF and UW))] AND [strategy_3: (user has NOT started TX)] AND [strategy_4: (user does NOT have PCaMETASTASIZE)]", 
      "function_details": {
        "function": "combine_strategies", 
        "kwargs": [
          {
            "name": "strategy_1", 
            "value": "allow_if_not_in_intervention"
          }, 
          {
            "name": "strategy_1_kwargs", 
            "value": [
              {
                "name": "intervention_name", 
                "value": "sexual_recovery"
              }
            ]
          }, 
          {
            "name": "strategy_2", 
            "value": "combine_strategies"
          }, 
          {
            "name": "strategy_2_kwargs", 
            "value": [
              {
                "name": "combinator", 
                "value": "any"
              }, 
              {
                "name": "strategy_1", 
                "value": "not_in_clinic_list"
              }, 
              {
                "name": "strategy_1_kwargs", 
                "value": [
                  {
                    "name": "org_list", 
                    "value": [
                      "UCSF Medical Center"
                    ]
                  }
                ]
              }, 
              {
                "name": "strategy_2", 
                "value": "limit_by_clinic_list"
              }, 
              {
                "name": "strategy_2_kwargs", 
                "value": [
                  {
                    "name": "org_list", 
                    "value": [
                      "UW Medicine (University of Washington)", 
                      "UCSF Medical Center"
                    ]
                  }
                ]
              }
            ]
          }, 
          {
            "name": "strategy_3", 
            "value": "observation_check"
          }, 
          {
            "name": "strategy_3_kwargs", 
            "value": [
              {
                "name": "display", 
                "value": "treatment begun"
              }, 
              {
                "name": "boolean_value", 
                "value": "false"
              }
            ]
          }, 
          {
            "name": "strategy_4", 
            "value": "observation_check"
          }, 
          {
            "name": "strategy_4_kwargs", 
            "value": [
              {
                "name": "display", 
                "value": "PCa localized diagnosis"
              }, 
              {
                "name": "boolean_value", 
                "value": "true"
              }
            ]
          }
        ]
      }

Communication
=============

Communicate from an intervention to any group of TrueNTH users via the
``/api/intervention/<intervention_name>/communicate`` `endpoint
<https://stg.us.truenth.org/dist/#!/Intervention/intervention_communicate>`__.

The `groups API <https://stg.us.truenth.org/dist/#!/Group>`_ is used to
view existing and create new groups.  Add existing users via the
``/api/user/<user_id>/groups`` `endpoint
<https://stg.us.truenth.org/dist/#!/Group/set_user_groups>`_.
