from collections import OrderedDict

from flask import Blueprint, redirect, render_template, url_for

from ..models.user import current_user
from ..views.external_assets import asset_by_uuid, get_any_tag_data

exercise_diet = Blueprint(
    'exercise_diet', __name__, template_folder='templates',
    static_folder='static', static_url_path='/exercise_diet/static',
    url_prefix='/exercise-and-diet')


def get_all_recipes():
    recipe_data = get_any_tag_data("recipe")
    recipe_assets = {'vegetables': [],
                     'healthy_vegetable_fat': [],
                     'tomatoes': [],
                     'fish': [],
                     'alternatives_to_processed_meats': []}
    for asset in recipe_data['results']:
        if 'vegetables' in asset['tags']:
            recipe_assets['vegetables'].append(
                (asset['title'], asset['uuid'],
                 asset['small_image'], 'recipe'))
        if 'healthy_vegetable_fat' in asset['tags']:
            recipe_assets['healthy_vegetable_fat'].append(
                (asset['title'], asset['uuid'],
                 asset['small_image'], 'recipe'))
        if 'tomatoes' in asset['tags']:
            recipe_assets['tomatoes'].append(
                (asset['title'], asset['uuid'],
                 asset['small_image'], 'recipe'))
        if 'fish' in asset['tags']:
            recipe_assets['fish'].append(
                (asset['title'], asset['uuid'],
                 asset['small_image'], 'recipe'))
        if 'alternatives_to_processed_meats' in asset['tags']:
            recipe_assets['alternatives_to_processed_meats'].append(
                (asset['title'], asset['uuid'],
                 asset['small_image'], 'recipe'))

    shopping_data = get_any_tag_data("shopping_tips")
    for asset in shopping_data['results']:
        if 'vegetables' in asset['tags']:
            recipe_assets['vegetables'].append(
                (asset['title'], asset['uuid'],
                 asset['small_image'], 'tip'))
        if 'healthy_vegetable_fat' in asset['tags']:
            recipe_assets['healthy_vegetable_fat'].append(
                (asset['title'], asset['uuid'],
                 asset['small_image'], 'tip'))
        if 'tomatoes' in asset['tags']:
            recipe_assets['tomatoes'].append(
                (asset['title'], asset['uuid'],
                 asset['small_image'], 'tip'))
        if 'fish' in asset['tags']:
            recipe_assets['fish'].append(
                (asset['title'], asset['uuid'],
                 asset['small_image'], 'tip'))
        if 'alternatives_to_processed_meats' in asset['tags']:
            recipe_assets['alternatives_to_processed_meats'].append(
                (asset['title'], asset['uuid'],
                 asset['small_image'], 'tip'))

    return recipe_assets


@exercise_diet.route('/')
def index():
    return redirect(url_for('exercise_diet.introduction'))


@exercise_diet.route('/introduction')
def introduction():
    assets = []
    data = get_any_tag_data("introduction")
    for asset in data['results']:
        assets.append(asset_by_uuid(asset['uuid']))

    return render_template('exercise_diet/index.html', assets=assets,
                           user=current_user())


@exercise_diet.route('/diet')
def diet():
    data = get_any_tag_data("diet")
    assets = []
    for asset in data['results']:
        assets.append(asset_by_uuid(asset['uuid']))

    modal_data = get_any_tag_data("diet-modal")
    modals = OrderedDict()
    for modal in modal_data['results']:
        tag = modal['tags']
        tag.remove('diet-modal')
        modals[tag[0]] = (modal['title'], modal['priority'],
                          asset_by_uuid(modal['uuid']))

    return render_template('exercise_diet/diet.html', assets=assets,
                           modals=modals, user=current_user())


@exercise_diet.route('/portal')
def portal():
    return render_template(
        'exercise_diet/exercise-diet_portal.html', user=current_user())


@exercise_diet.route('/exercise')
def exercise():
    data = get_any_tag_data("exercise")
    assets = []
    for asset in data['results']:
        assets.append(asset_by_uuid(asset['uuid']))

    modal_data = get_any_tag_data("exercise-modal")
    modals = OrderedDict()
    for modal in modal_data['results']:
        tag = modal['tags']
        tag.remove('exercise-modal')
        modals[tag[0]] = (modal['title'], modal['priority'],
                          asset_by_uuid(modal['uuid']))

    return render_template('exercise_diet/exercise.html', assets=assets,
                           modals=modals, user=current_user())


@exercise_diet.route('/recipes')
def recipes():
    data = get_any_tag_data("recipe-intro")
    recipe_intro = asset_by_uuid(data['results'][0]['uuid'])
    recipe_assets = get_all_recipes()
    return render_template('exercise_diet/recipes.html',
                           recipe_intro=recipe_intro,
                           recipe_assets=recipe_assets,
                           user=current_user())


@exercise_diet.route('/recipe/<heading>/<int:item>')
def recipe(heading, item):
    assets = get_all_recipes()
    asset = asset_by_uuid(assets[heading][item][1])

    ordered_headings = ['healthy_vegetable_fat', 'vegetables', 'tomatoes',
                        'fish', 'alternatives_to_processed_meats']
    current_heading_item_count = len(assets[heading])
    prev_heading = ''
    next_heading = ''
    prev_item_index = ''
    next_item_index = ''
    prev_asset_title = ''
    next_asset_title = ''
    next_asset_recipe_type = ''
    prev_asset_recipe_type = ''
    if item == 0:
        prev_heading_index = ordered_headings.index(heading) - 1
        if prev_heading_index >= 0:
            prev_heading = ordered_headings[prev_heading_index]
            prev_item_index = len(assets[prev_heading]) - 1
            prev_asset_title = assets[prev_heading][prev_item_index][0]
            prev_asset_recipe_type = assets[prev_heading][prev_item_index][2]
        next_item_index = item + 1
        next_heading = heading
        next_asset_title = assets[heading][item + 1][0]
        next_asset_recipe_type = assets[heading][item + 1][2]
    elif item == current_heading_item_count - 1:
        if ordered_headings.index(heading) + 2 <= len(ordered_headings):
            next_item_index = 0
            next_heading_index = ordered_headings.index(heading) + 1
            next_heading = ordered_headings[next_heading_index]
            next_asset_title = assets[next_heading][0][0]
            next_asset_recipe_type = assets[next_heading][0][2]
        prev_heading = heading
        prev_item_index = item - 1
        prev_asset_title = assets[heading][item - 1][0]
        prev_asset_recipe_type = assets[heading][item - 1][2]
    else:
        next_heading = heading
        prev_heading = heading
        prev_item_index = item - 1
        next_item_index = item + 1
        prev_asset_title = assets[heading][prev_item_index][0]
        next_asset_title = assets[heading][next_item_index][0]
        next_asset_recipe_type = assets[heading][next_item_index][2]
        prev_asset_recipe_type = assets[heading][prev_item_index][2]

    return render_template('exercise_diet/recipe.html',
                           asset=asset,
                           prev_heading=prev_heading,
                           next_heading=next_heading,
                           prev_item_index=prev_item_index,
                           next_item_index=next_item_index,
                           prev_asset_title=prev_asset_title,
                           next_asset_title=next_asset_title,
                           next_asset_recipe_type=next_asset_recipe_type,
                           prev_asset_recipe_type=prev_asset_recipe_type)
