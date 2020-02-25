"""Views used to obtain external assets

Primarily LifeRay content access - via exposed APIs for portal side caching
"""
from flask import Blueprint, current_app, request
from ..models.app_text import localize_url, time_request

asset_api = Blueprint('asset', __name__)


def get_request(url, params=None):
    """helper for returning response data from requested URL in JSON

    :param url: the URL to pull content from
    :param params: optional, if provided, use as
        parameters to the requested URL

    """
    try:
        response = time_request(url, params).json()
    except ValueError:  # raised when no json is available in response
        current_app.logger.error(
            "Request did not return json: {}".format(url))
        raise

    return response


def lr_query_url():
    return '/'.join((
        current_app.config["LR_ORIGIN"], 'c/portal/truenth/asset/query'))


def lr_detailed_url():
    return '/'.join((
        current_app.config["LR_ORIGIN"], 'c/portal/truenth/asset/detailed'))


@asset_api.route('/api/asset/tag/<tag>', methods=('GET',))
def asset_by_tag(tag):
    url = localize_url(lr_query_url(), request.args.get('locale_code', 'en'))
    params = {
        'allTags': tag,
        'index': request.args.get('index', 0),
        'content': 'true',
        'version': 'latest',
    }
    response = get_request(url, params)
    # Exception will result if no matching key or content
    return response['results'][0]['content']


@asset_api.route('/api/asset/uuid/<uuid>', methods=('GET',))
def asset_by_uuid(uuid):
    url = localize_url(
        lr_detailed_url(), request.args.get('locale_code', 'en'))
    params = {
        'uuid': uuid,
        'version': 'latest',
    }
    response = get_request(url, params)
    # This will fail noisily if no matching key
    return response['asset']


@asset_api.route('/api/asset/tag/any', methods=('GET',))
def get_any_tag_data(*anyTags):
    """ query LR based on any tags

    this is an OR condition; will match any tag specified

    :param anyTag: a variable number of tags to be queried,
         e.g., 'tag1', 'tag2'

    """
    # NOTE: need to convert tags to format: anyTags=tag1&anyTags=tag2...
    liferay_qs_params = {
        'anyTags': anyTags,
        'sort': 'true',
        'sortType': 'DESC'
    }
    return get_request(lr_query_url(), params=liferay_qs_params)


def get_all_tag_data(*allTags):
    """ query LR based on all required tags

    this is an AND condition; all required tags must be present

    :param allTags: variable number of tags to be queried,
        e.g., 'tag1', 'tag2'

    """
    # NOTE: need to convert tags to format: allTags=tag1&allTags=tag2...
    liferay_qs_params = {
        'allTags': allTags,
        'sort': 'true',
        'sortType': 'DESC'
    }
    return get_request(lr_query_url(), params=liferay_qs_params)
