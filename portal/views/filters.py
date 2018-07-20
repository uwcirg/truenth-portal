from flask import Blueprint, current_app
import jinja2

filters_blueprint = Blueprint('filters', __name__)


@jinja2.contextfilter
@filters_blueprint.app_template_filter()
def show_macro(context, value, name, user=None):
    """ Custom filter to show or hide macros depending on configuration """
    if name in current_app.config.get('SHOW_PROFILE_MACROS', []):
        return value
    return ''
