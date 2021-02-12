from collections import defaultdict
from flask_webtest import SessionScope
import json
import os
from pytest import fixture

from portal.database import db
from portal.models.observation import Observation
from portal.trigger_states.empro_domains import DomainManifold


def json_from_file(request, filename):
    data_dir, _ = os.path.splitext(request.module.__file__)
    with open(os.path.join(data_dir, filename), 'r') as json_file:
        data = json.load(json_file)
    return data


@fixture
def obs_w_extension(request):
    filename = 'obs-w-extension.json'
    return json_from_file(request=request, filename=filename)


@fixture
def obs_bundle(request):
    filename = 'obs-bundle.json'
    return json_from_file(request=request, filename=filename)


@fixture
def obs_bundle_sans_extension(request):
    filename = 'obs-bundle-sans-extension.json'
    return json_from_file(request=request, filename=filename)


def test_coding_extension(initialized_with_ss_qnr, obs_w_extension):
    obs = Observation()
    obs.update_from_fhir(obs_w_extension)

    # Questionnaire Domain resides in `codeable_concept.codings`
    need_to_see = set([
        ('ironman_ss', 'http://us.truenth.org/questionnaire'),
        ('joint_pain', 'http://us.truenth.org/observation')])
    seen = set()
    for coding in obs.codeable_concept.codings:
        seen.add((coding.code, coding.system))
    assert not seen.difference(need_to_see)

    # valueCoding holds the answer, and it's extension, a trigger value
    assert obs.value_coding.code == 'ironman_ss.4.4'
    assert obs.value_coding.extension.code == 'penultimate'


def test_query_obs_from_qnr(initialized_with_ss_qnr, obs_w_extension):
    obs = Observation()
    obs.update_from_fhir(obs_w_extension)

    with SessionScope(db):
        db.session.add(obs)
        db.session.commit()

    qnr = db.session.merge(initialized_with_ss_qnr)
    obs = Observation.query.filter(Observation.derived_from == str(qnr.id))
    assert obs.one()


def test_obtain_observations(obs_w_extension, initialized_with_ss_qnr):
    obs = Observation()
    obs.update_from_fhir(obs_w_extension)

    with SessionScope(db):
        db.session.add(obs)
        db.session.commit()

    qnr = db.session.merge(initialized_with_ss_qnr)
    dm = DomainManifold(qnr)
    assert dm.cur_obs['joint_pain']['ironman_ss.4'] == (4, 'penultimate')


def test_parse_bundle(obs_bundle_sans_extension, initialized_with_ss_qnr):
    Observation.parse_obs_bundle(obs_bundle_sans_extension)
    expect = {
        'anxious',
        'discouraged',
        'fatigue',
        'general_pain',
        'insomnia',
        'joint_pain',
        'sad',
        'social_isolation'}
    found_domains = set()
    for ob in Observation.query.all():
        found_domains.add(ob.codeable_concept.codings[0].code)
    assert found_domains == expect


def test_parse_bundle_extensions(obs_bundle, initialized_with_ss_qnr):
    Observation.parse_obs_bundle(obs_bundle)
    found_extensions = defaultdict(int)
    for ob in Observation.query.all():
        if ob.value_coding and ob.value_coding.extension_id:
            found_extensions[ob.value_coding.extension.code] += 1

    assert found_extensions['ultimate'] == 8
    assert found_extensions['penultimate'] == 11
