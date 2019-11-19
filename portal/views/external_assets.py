"""Views used to obtain external assets

Primarily LifeRay content access - via exposed APIs for portal side caching
"""
from flask import Blueprint, current_app, request
from requests.exceptions import ConnectionError
from ..models.app_text import localize_url, time_request

asset_api = Blueprint('asset', __name__)

 """helper for fetching response data from requested URL

        :param url: the URL to pull details and asset from
        :param params: optional, if provided, use as
            parameters to the requested URL

"""
def get_request(url, params=None):
    error_msg = ''
    try:
        response = time_request(url, params).json()
    except ValueError:  # raised when no json is available in response
        if response.status_code == 200:
            return response.text
        else:
            error_msg = (
                "Could not retrieve remote content - " "{} {}".format(
                    response.status_code, response.reason))
    except ConnectionError:
            error_msg = (
            "Could not retrieve remove content - Server could not be "
            "reached")
    if error_msg:
        current_app.logger.error(error_msg + ": {}".format(url))
    return response, error_msg


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
    response, error_msg = get_request(url, params)
    if error_msg: 
        return error_msg
    if isinstance(response, dict):
        if not response['results'] or not len(response['results']):
            abort(404, 'Remote content not found for tag {}'.format(tag))
        return response['results'][0]['content']
    # response is text string, just return it
    return response


@asset_api.route('/api/asset/uuid/<uuid>', methods=('GET',))
def by_uuid(uuid):
    url = "{}/c/portal/truenth/asset/detailed".format(
        current_app.config["LR_ORIGIN"])
    url = localize_url(url, request.args.get('locale_code', 'en'))
    params = {
        'uuid': uuid,
        'version': 'latest',
    }
    response, error_msg = get_request(url, params)
    if error_msg:
        return error_msg
    if isinstance(response, dict):
        if not response['asset']:
            abort(404, 'Remote content not found for uuid {}'.format(uuid))
        return response['asset']
    # response is text string, just return it
    return response
