import requests
import json
from flask import Blueprint, Flask, render_template, redirect, url_for


exercise_diet = Blueprint(
    'exercise_diet', __name__, template_folder='templates',
    static_folder='static', static_url_path='/exercise_diet/static')


def get_asset(uuid):
    url = "https://stg-lr7.us.truenth.org/c/portal/truenth/asset/detailed?version=latest&uuid=%s" % uuid
    data = requests.get(url).content
    return json.JSONDecoder().decode(data)['asset']


def get_all_recipes():
    url = "https://stg-lr7.us.truenth.org/c/portal/truenth/asset/query?anyTags=recipe"
    recipe_data = requests.get(url).content
    recipe_assets = {'vegetables': [], 'healthy_vegetable_fat': [], 'tomatoes': [], 'fish': [],
                     'alternatives_to_processed_meats': []}
    for asset in json.JSONDecoder().decode(recipe_data)['results']:
        if 'vegetables' in asset['tags']:
            recipe_assets['vegetables'].append((asset['title'], asset['uuid']))
        if 'healthy_vegetable_fat' in asset['tags']:
            recipe_assets['healthy_vegetable_fat'].append((asset['title'], asset['uuid']))
        if 'tomatoes' in asset['tags']:
            recipe_assets['tomatoes'].append((asset['title'], asset['uuid']))
        if 'fish' in asset['tags']:
            recipe_assets['fish'].append((asset['title'], asset['uuid']))
        if 'alternatives_to_processed_meats' in asset['tags']:
            recipe_assets['alternatives_to_processed_meats'].append((asset['title'], asset['uuid']))

    shopping_url = "https://stg-lr7.us.truenth.org/c/portal/truenth/asset/query?anyTags=shopping_tips"
    shopping_data = requests.get(shopping_url).content
    for asset in json.JSONDecoder().decode(shopping_data)['results']:
        if 'vegetables' in asset['tags']:
            recipe_assets['vegetables'].append((asset['title'], asset['uuid']))
        if 'healthy_vegetable_fat' in asset['tags']:
            recipe_assets['healthy_vegetable_fat'].append((asset['title'], asset['uuid']))
        if 'tomatoes' in asset['tags']:
            recipe_assets['tomatoes'].append((asset['title'], asset['uuid']))
        if 'fish' in asset['tags']:
            recipe_assets['fish'].append((asset['title'], asset['uuid']))
        if 'alternatives_to_processed_meats' in asset['tags']:
            recipe_assets['alternatives_to_processed_meats'].append((asset['title'], asset['uuid']))

    return recipe_assets

@exercise_diet.route('/')
def index():
    return redirect(url_for('exercise_diet.introduction'))


@exercise_diet.route('/introduction')
def introduction():
    url = "https://stg-lr7.us.truenth.org/c/portal/truenth/asset/query?anyTags=introduction"
    data = requests.get(url).content
    assets = []
    for asset in json.JSONDecoder().decode(data)['results']:
        assets.append(get_asset(asset['uuid']))

    return render_template('exercise_diet/index.html', assets=assets)


@exercise_diet.route('/diet')
def diet():
    url = "https://stg-lr7.us.truenth.org/c/portal/truenth/asset/query?anyTags=diet"
    data = requests.get(url).content
    assets = []
    for asset in json.JSONDecoder().decode(data)['results']:
        assets.append(get_asset(asset['uuid']))

    url = "https://stg-lr7.us.truenth.org/c/portal/truenth/asset/query?anyTags=diet-modal"
    modal_data = requests.get(url).content
    modals = {}
    for modal in json.JSONDecoder().decode(modal_data)['results']:
        tag = modal['tags']
        tag.remove('diet-modal')
        modals[tag[0]] = get_asset(modal['uuid'])

    return render_template('exercise_diet/diet.html', assets=assets, modals=modals)


@exercise_diet.route('/exercise')
def exercise():
    url = "https://stg-lr7.us.truenth.org/c/portal/truenth/asset/query?anyTags=exercise"
    data = requests.get(url).content
    assets = []
    for asset in json.JSONDecoder().decode(data)['results']:
        assets.append(get_asset(asset['uuid']))

    url = "https://stg-lr7.us.truenth.org/c/portal/truenth/asset/query?anyTags=exercise-modal"
    modal_data = requests.get(url).content
    modals = {}
    for modal in json.JSONDecoder().decode(modal_data)['results']:
        tag = modal['tags']
        tag.remove('exercise-modal')
        modals[tag[0]] = get_asset(modal['uuid'])

    return render_template('exercise_diet/exercise.html', assets=assets, modals=modals)


@exercise_diet.route('/resources')
def resources():
    url = "https://stg-lr7.us.truenth.org/c/portal/truenth/asset/query?anyTags=resources"
    data = requests.get(url).content
    assets = []
    for asset in json.JSONDecoder().decode(data)['results']:
        assets.append(get_asset(asset['uuid']))

    return render_template('exercise_diet/resources.html', assets=assets)


@exercise_diet.route('/recipes')
def recipes():
    recipe_assets = get_all_recipes()
    return render_template('exercise_diet/recipes.html', recipe_assets=recipe_assets)


@exercise_diet.route('/recipe/<heading>/<int:item>')
def recipe(heading, item):
    assets = get_all_recipes()
    asset = get_asset(assets[heading][item][1])

    ordered_headings = ['healthy_vegetable_fat', 'vegetables', 'tomatoes', 'fish', 'alternatives_to_processed_meats']
    current_heading_item_count = len(assets[heading])
    prev_heading = ''
    next_heading = ''
    prev_item_index = ''
    next_item_index = ''
    prev_asset_title = ''
    next_asset_title = ''
    if item == 0:
        prev_heading_index = ordered_headings.index(heading) - 1
        if prev_heading_index >= 0:
            prev_heading = ordered_headings[prev_heading_index]
            prev_item_index = len(assets[prev_heading]) - 1
            prev_asset_title = assets[prev_heading][prev_item_index][0]
        next_item_index = item + 1
        next_heading = heading
        next_asset_title = assets[heading][item + 1][0]
    elif item == current_heading_item_count - 1:
        if ordered_headings.index(heading) + 2 <= len(ordered_headings):
            next_item_index = 0
            next_heading_index = ordered_headings.index(heading) + 1
            next_heading = ordered_headings[next_heading_index]
            next_asset_title = assets[next_heading][0][0]
        prev_heading = heading
        prev_item_index = item - 1
        prev_asset_title = assets[heading][item - 1][0]
    else:
        next_heading = heading
        prev_heading = heading
        prev_item_index = item - 1
        next_item_index = item + 1
        prev_asset_title = assets[heading][prev_item_index][0]
        next_asset_title = assets[heading][next_item_index][0]

    return render_template('exercise_diet/recipe.html',
                           asset=asset,
                           prev_heading=prev_heading,
                           next_heading=next_heading,
                           prev_item_index=prev_item_index,
                           next_item_index=next_item_index,
                           prev_asset_title=prev_asset_title,
                           next_asset_title=next_asset_title)
