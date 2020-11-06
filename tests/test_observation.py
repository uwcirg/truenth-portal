import json
import os
from pytest import fixture

from portal.models.observation import Observation


def json_from_file(request, filename):
    data_dir, _ = os.path.splitext(request.module.__file__)
    with open(os.path.join(data_dir, filename), 'r') as json_file:
        data = json.load(json_file)
    return data


@fixture
def obs_w_extension(request):
    filename = 'obs-w-extension.json'
    return json_from_file(request=request, filename=filename)


def test_coding_extension(obs_w_extension):
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
