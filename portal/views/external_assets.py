"""Views used to obtain external assets

Primarily LifeRay content access - via exposed APIs for portal side caching
"""
from flask import Blueprint, current_app, request
from requests.exceptions import ConnectionError
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


@asset_api.route('/api/asset/tag/<tag>', methods=('GET',))
def by_tag(tag):
    url = "{}/c/portal/truenth/asset/query".format(
        current_app.config["LR_ORIGIN"])
    url = localize_url(url, request.args.get('locale_code', 'en'))
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
def by_uuid(uuid):
    url = "{}/c/portal/truenth/asset/detailed".format(
        current_app.config["LR_ORIGIN"])
    url = localize_url(url, request.args.get('locale_code', 'en'))
    params = {
        'uuid': uuid,
        'version': 'latest',
    }
    response = get_request(url, params)

    # This will fail noisily if no matching key
    return response['asset']

