import requests
import json
from flask import Blueprint, current_app, render_template

exercise_diet = Blueprint(
    'exercise_diet', __name__, template_folder='templates', static_folder='static',
    static_url_path='/exercise_diet/static')


def get_asset(uuid):
    url = (
        "{LR_ORIGIN}/c/portal/truenth/asset/detailed?version=latest&"
        "uuid={uuid}".format(LR_ORIGIN=current_app.config.get('LR_ORIGIN'),
                             uuid=uuid))
    data = requests.get(url).content
    return json.JSONDecoder().decode(data)['asset']


def get_assets_from_tag(tag):
    """Given single tag, queries LR and returns matching list of assets"""
    url = "{LR_ORIGIN}/c/portal/truenth/asset/query?anyTags={tag}".format(
        LR_ORIGIN=current_app.config.get('LR_ORIGIN'), tag=tag)
    data = requests.get(url).content
    assets = []
    for asset in json.JSONDecoder().decode(data)['results']:
        assets.append(get_asset(asset['uuid']))
    return assets


@exercise_diet.route('/chcr')
def index():
    return render_template('exercise_diet/index.html')


@exercise_diet.route('/diet')
def diet():
    return render_template(
        'exercise_diet/diet.html', assets=get_assets_from_tag('diet'))


@exercise_diet.route('/exercise')
def exercise():
    return render_template(
        'exercise_diet/exercise.html', assets=get_assets_from_tag('exercise'))


@exercise_diet.route('/resources')
def resources():
    return render_template(
        'exercise_diet/resources.html', assets=get_assets_from_tag('resources'))


@exercise_diet.route('/recipes')
def recipes():
    return render_template(
        'exercise_diet/recipes.html', assets=get_assets_from_tag('recipe'))
