"""Views used to obtain external assets

Primarily LifeRay content access - via exposed APIs for portal side caching
"""
from flask import Blueprint, current_app
import requests

assets_api = Blueprint('assets', __name__)


@assets_api.route('/api/assets/tag/<tag>', methods=('GET',))
def by_tag(tag):
    url = "{}/c/portal/truenth/asset/query".format(
        current_app.config["LR_ORIGIN"])
    return requests.get(
        url, params={'allTags': tag, 'returnFirst': True}).json()['asset']


@assets_api.route('/api/assets/uuid/<uuid>', methods=('GET',))
def by_uuid(uuid):
    url = "{}/c/portal/truenth/asset/detailed".format(
        current_app.config["LR_ORIGIN"])
    return requests.get(url, params={'uuid': uuid}).json()['asset']
