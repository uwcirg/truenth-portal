"""Unit test module for Clinical API"""

from datetime import datetime, timedelta
import json
import os
import sys

from dateutil import parser
from flask_webtest import SessionScope
import pytest

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.codeable_concept import CodeableConcept
from portal.models.coding import Coding
from portal.models.encounter import Encounter
from portal.models.observation import Observation, UserObservation
from portal.models.performer import Performer
from portal.models.reference import Reference
from portal.models.user import User
from portal.models.value_quantity import ValueQuantity
from tests import TEST_USER_ID 


def prep_db_for_clinical():
    # First push some clinical data into the db for the test user
    with SessionScope(db):
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        observation = Observation()
        coding = Coding(system='SNOMED-CT', code='372278000',
                        display='Gleason score')
        gleason_concept = CodeableConcept(codings=[coding, ])
        observation.codeable_concept = gleason_concept
        observation.value_quantity = ValueQuantity(value=2)
        performer = Performer(reference_txt=json.dumps(
            Reference.patient(TEST_USER_ID).as_fhir()))
        observation.performers.append(performer)
        db.session.add(observation)
        enc = Encounter(status='planned', auth_method='url_authenticated',
                        user_id=TEST_USER_ID, start_time=datetime.utcnow())
        db.session.add(enc)
        db.session.flush()
        db.session.add(UserObservation(user_id=int(TEST_USER_ID),
                                       observation_id=observation.id,
                                       encounter_id=enc.id, audit=audit))
        db.session.commit()
    return gleason_concept

def test_datetime_for_concept(test_user):
    gleason_concept = prep_db_for_clinical()
    gleason_concept = db.session.merge(gleason_concept)
    test_user = db.session.merge(test_user)
    assert (pytest.approx(datetime.utcnow().toordinal()) ==
            test_user.fetch_datetime_for_concept(
                gleason_concept).toordinal())

def test_clinicalGET(login, client, test_user):
    prep_db_for_clinical()
    login()
    response = client.get('/api/patient/%s/clinical' % TEST_USER_ID)

    clinical_data = response.json
    assert ('Gleason score' ==
            clinical_data['entry'][0]['content']['code']['coding'][0][
               'display'])
    assert ('2' ==
            clinical_data['entry'][0]['content']['valueQuantity']['value'])
    assert (json.dumps(Reference.patient(TEST_USER_ID).as_fhir())
            == clinical_data['entry'][0]['content']['performer'][0])
    found = parser.parse(clinical_data['entry'][0]['updated'])
    found = found.replace(tzinfo=None)
    assert (abs(datetime.utcnow() - found) <= timedelta(seconds=5))

def test_dstu2GET(login, client, test_user):
    prep_db_for_clinical()
    login()
    response = client.get(
        '/api/patient/%s/clinical' % TEST_USER_ID,
        query_string={'patch_dstu2': True})

    clinical_data = response.json
    assert len(clinical_data['entry']) == 1
    assert 'resource' in clinical_data['entry'][0]
    assert ('Gleason score' ==
            clinical_data['entry'][0]['resource']['code']['coding'][0][
               'display'])
    assert ('2' == clinical_data['entry'][0][
        'resource']['valueQuantity']['value'])
    assert (json.dumps(Reference.patient(TEST_USER_ID).as_fhir())
            == clinical_data['entry'][0]['resource']['performer'][0])

def test_clinicalPOST(login, client, test_user):
    data = {
        "resourceType": "Observation",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "28540-3",
                "display": ("Erythrocyte mean corpuscular hemoglobin "
                            "concentration [Mass/volume]")
            }]},
        "valueQuantity": {
            "value": 18.7,
            "units": "g/dl",
            "system": "http://unitsofmeasure.org",
            "code": "g/dl"
        },
        "status": "final",
        "issued": "2015-08-04T13:27:00+01:00",
        "performer": Reference.patient(TEST_USER_ID).as_fhir()
    }

    login()
    response = client.post(
        '/api/patient/%s/clinical' % TEST_USER_ID,
        content_type='application/json', data=json.dumps(data))
    assert response.status_code == 200
    fhir = response.json
    assert '28540-3' in fhir['message']
    assert test_user.observations.count() == 1
    uo = UserObservation.query.filter_by(user_id=TEST_USER_ID).one()
    assert uo.encounter.auth_method == 'password_authenticated'

def test_int_code_POST(login, client, test_user):
    data = {
        "resourceType": "Observation",
        "code": {
            "coding": [{
                "code": 111,
                "display": "biopsy",
                "system": "http://us.truenth.org/clinical-codes"}]},
        "issued": "2018-01-1",
        "status": "",
        "valueQuantity": {
            "units": "boolean",
            "value": "true"}}

    login()
    response = client.post(
        '/api/patient/%s/clinical' % TEST_USER_ID,
        content_type='application/json', data=json.dumps(data))
    assert response.status_code == 200
    assert '111' in response.json['message']
    assert test_user.observations.count() == 1

def test_clinicalPUT(login, client, test_user):
    prep_db_for_clinical()
    login()
    obs = Observation.query.first()
    new_issued = '2016-06-06T06:06:06'
    data = {'status': 'unknown', 'issued': new_issued}
    data['valueQuantity'] = {'units': 'boolean', 'value': 'false'}
    response = client.put('/api/patient/{}/clinical/{}'.format(
        TEST_USER_ID, obs.id), content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 200
    clinical_data = response.json
    assert clinical_data['status'] == 'unknown'
    assert clinical_data['issued'] == new_issued + "+00:00"  # tz
    assert clinical_data['valueQuantity']['value'] == 'false'

def test_clinical0forFalse(login, client, test_user):
    prep_db_for_clinical()
    login()
    obs = Observation.query.first()
    new_issued = '2016-06-06T06:06:06'
    data = {'status': 'unknown', 'issued': new_issued}
    data['valueQuantity'] = {'units': 'boolean', 'value': 0}
    response = client.put('/api/patient/{}/clinical/{}'.format(
        TEST_USER_ID, obs.id), content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 200
    clinical_data = response.json
    assert clinical_data['status'] == 'unknown'
    assert clinical_data['issued'] == new_issued + "+00:00"  # tz
    assert clinical_data['valueQuantity']['value'] == 'false'

def test_empty_clinical_get(login, client, test_user):
    """Access clinical on user w/o any clinical info"""
    login()
    response = client.get('/api/patient/%s/clinical' % TEST_USER_ID)
    assert response.status_code == 200

def test_unknown_clinical_post(login, client, test_user):
    login()
    data = {
        "resourceType": "Observation",
        "code": {"coding": [{
            "code": "121",
            "display": "PCa diagnosis",
            "system": "http://us.truenth.org/clinical-codes"}]},
        "status": "unknown",
        "valueQuantity": {"units": "boolean", "value": None}}
    response = client.post('/api/patient/{}/clinical'.format(
        TEST_USER_ID), content_type='application/json',
        data=json.dumps(data))

    # confirm status unknown sticks
    assert response.status_code == 200
    response = client.get('/api/patient/%s/clinical' % TEST_USER_ID)
    assert 'unknown' == response.json['entry'][0]['content']['status']

def test_empty_biopsy_get(login, client, test_user):
    """Access biopsy on user w/o any clinical info"""
    login()
    response = client.get('/api/patient/%s/clinical/biopsy'
                               % TEST_USER_ID)
    assert response.status_code == 200
    data = response.json
    assert data['value'] == 'unknown'

def test_clinical_biopsy_put(login, client, test_user):
    """Shortcut API - just biopsy data w/o FHIR overhead"""
    login()
    response = client.post(
        '/api/patient/%s/clinical/biopsy' % TEST_USER_ID,
        content_type='application/json', data=json.dumps({'value': True}))
    assert response.status_code == 200
    result = response.json
    assert result['message'] == 'ok'

    # Can we get it back in FHIR?
    response = client.get('/api/patient/%s/clinical' % TEST_USER_ID)
    data = response.json
    coding = data['entry'][0]['content']['code']['coding'][0]
    vq = data['entry'][0]['content']['valueQuantity']

    assert coding['code'] == '111'
    assert coding['display'] == 'biopsy'
    assert coding['system'] == 'http://us.truenth.org/clinical-codes'
    assert vq['value'] == 'true'

    # Access the direct biopsy value
    response = client.get('/api/patient/%s/clinical/biopsy'
                               % TEST_USER_ID)
    data = response.json
    assert data['value'] == 'true'

    # Can we alter the value?
    response = client.post(
        '/api/patient/%s/clinical/biopsy' % TEST_USER_ID,
        content_type='application/json', data=json.dumps({'value': False}))
    assert response.status_code == 200
    result = response.json
    assert result['message'] == 'ok'

    # Confirm it's altered
    response = client.get('/api/patient/%s/clinical/biopsy'
                               % TEST_USER_ID)
    data = response.json
    assert data['value'] == 'false'

    # Confirm history is retained
    user = User.query.get(TEST_USER_ID)
    assert user.observations.count() == 2

def test_clinical_biopsy_unknown(login, client, test_user):
    """Shortcut API - biopsy data w status unknown"""
    login()
    response = client.post(
        '/api/patient/%s/clinical/biopsy' % TEST_USER_ID,
        content_type='application/json',
        data=json.dumps({'value': True, 'status': 'unknown'}))
    assert response.status_code == 200
    result = response.json
    assert result['message'] == 'ok'

    # Can we get it back in FHIR?
    response = client.get('/api/patient/%s/clinical' % TEST_USER_ID)
    data = response.json
    coding = data['entry'][0]['content']['code']['coding'][0]
    vq = data['entry'][0]['content']['valueQuantity']
    status = data['entry'][0]['content']['status']

    assert coding['code'] == '111'
    assert coding['display'] == 'biopsy'
    assert coding['system'] == 'http://us.truenth.org/clinical-codes'
    assert vq['value'] == 'true'
    assert status == 'unknown'

    # Access the direct biopsy value
    response = client.get('/api/patient/%s/clinical/biopsy'
                               % TEST_USER_ID)
    data = response.json
    assert data['value'] == 'unknown'

    # Can we alter the value?
    response = client.post(
        '/api/patient/%s/clinical/biopsy' % TEST_USER_ID,
        content_type='application/json', data=json.dumps({'value': False}))
    assert response.status_code == 200
    result = response.json
    assert result['message'] == 'ok'

    # Confirm it's altered
    response = client.get('/api/patient/%s/clinical/biopsy'
                               % TEST_USER_ID)
    data = response.json
    assert data['value'] == 'false'

    # Confirm history is retained
    user = User.query.get(TEST_USER_ID)
    assert user.observations.count() == 2

def test_clinical_pca_diag(login, client, test_user):
    """Shortcut API - just PCa diagnosis w/o FHIR overhead"""
    login()
    response = client.post(
        '/api/patient/%s/clinical/pca_diag' % TEST_USER_ID,
        content_type='application/json',
        data=json.dumps({'value': True}))
    assert response.status_code == 200
    result = response.json
    assert result['message'] == 'ok'

    # Can we get it back in FHIR?
    response = client.get('/api/patient/%s/clinical' % TEST_USER_ID)
    data = response.json
    coding = data['entry'][0]['content']['code']['coding'][0]
    vq = data['entry'][0]['content']['valueQuantity']

    assert coding['code'] == '121'
    assert coding['display'] == 'PCa diagnosis'
    assert coding['system'] == 'http://us.truenth.org/clinical-codes'
    assert vq['value'] == 'true'

    # Access the direct pca_diag value
    response = client.get(
        '/api/patient/%s/clinical/pca_diag' % TEST_USER_ID)
    data = response.json
    assert data['value'] == 'true'

def test_clinical_pca_diag_unknown(login, client, test_user):
    """Shortcut API - PCa diagnosis w/ status unknown"""
    login()
    response = client.post(
        '/api/patient/%s/clinical/pca_diag' % TEST_USER_ID,
        content_type='application/json',
        data=json.dumps({'value': True, 'status': 'unknown'}))
    assert response.status_code == 200
    result = response.json
    assert result['message'] == 'ok'

    # Can we get it back in FHIR?
    response = client.get('/api/patient/%s/clinical' % TEST_USER_ID)
    data = response.json
    coding = data['entry'][0]['content']['code']['coding'][0]
    vq = data['entry'][0]['content']['valueQuantity']
    status = data['entry'][0]['content']['status']

    assert coding['code'] == '121'
    assert coding['display'] == 'PCa diagnosis'
    assert coding['system'] == 'http://us.truenth.org/clinical-codes'
    assert vq['value'] == 'true'
    assert status == 'unknown'

    # Access the direct pca_diag value
    response = client.get(
        '/api/patient/%s/clinical/pca_diag' % TEST_USER_ID)
    data = response.json
    assert data['value'] == 'unknown'

def test_clinical_pca_localized(login, client, test_user):
    """Shortcut API - just PCa localized diagnosis w/o FHIR overhead"""
    login()
    response = client.post(
        '/api/patient/%s/clinical/pca_localized' % TEST_USER_ID,
        content_type='application/json', data=json.dumps({'value': True}))
    assert response.status_code == 200
    result = response.json
    assert result['message'] == 'ok'

    # Can we get it back in FHIR?
    response = client.get('/api/patient/%s/clinical' % TEST_USER_ID)
    data = response.json
    coding = data['entry'][0]['content']['code']['coding'][0]
    vq = data['entry'][0]['content']['valueQuantity']

    assert coding['code'] == '141'
    assert coding['display'] == 'PCa localized diagnosis'
    assert coding['system'] == 'http://us.truenth.org/clinical-codes'
    assert vq['value'] == 'true'

    # Access the direct pca_localized value
    response = client.get(
        '/api/patient/%s/clinical/pca_localized' % TEST_USER_ID)
    data = response.json
    assert data['value'] == 'true'

def test_clinical_pca_localized_unknown(login, client, test_user):
    """Shortcut API - PCa localized diagnosis w status unknown"""
    login()
    response = client.post(
        '/api/patient/%s/clinical/pca_localized' % TEST_USER_ID,
        content_type='application/json',
        data=json.dumps({'value': False, 'status': 'unknown'}))
    assert response.status_code == 200
    result = response.json
    assert result['message'] == 'ok'

    # Can we get it back in FHIR?
    response = client.get('/api/patient/%s/clinical' % TEST_USER_ID)
    data = response.json
    coding = data['entry'][0]['content']['code']['coding'][0]
    vq = data['entry'][0]['content']['valueQuantity']
    status = data['entry'][0]['content']['status']

    assert coding['code'] == '141'
    assert coding['display'] == 'PCa localized diagnosis'
    assert coding['system'] == 'http://us.truenth.org/clinical-codes'
    assert vq['value'] == 'false'
    assert status == 'unknown'

    # Access the direct pca_localized value
    response = client.get(
        '/api/patient/%s/clinical/pca_localized' % TEST_USER_ID)
    data = response.json
    assert data['value'] == 'unknown'

def test_weight(login, client, test_user):
    with open(os.path.join(os.path.dirname(__file__),
                           'weight_example.json'), 'r') as fhir_data:
        data = json.load(fhir_data)

    login()
    response = client.put(
        '/api/patient/{}/clinical'.format(TEST_USER_ID),
        content_type='application/json', data=json.dumps(data))
    assert response.status_code == 200

    obs = test_user.observations.one()  # only expect the one
    assert '185' == obs.value_quantity.value
    assert 3 == len(obs.codeable_concept.codings)
