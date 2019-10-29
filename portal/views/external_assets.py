"""Views used to obtain external assets

Primarily LifeRay content access - via exposed APIs for portal side caching
"""
from flask import Blueprint, current_app
import requests

asset_api = Blueprint('asset', __name__)


@asset_api.route('/api/asset/tag/<tag>', methods=('GET',))
def by_tag(tag):
    url = "{}/c/portal/truenth/asset/query".format(
        current_app.config["LR_ORIGIN"])
    return requests.get(
        url, params={'allTags': tag, 'returnFirst': True}).json()['asset']


@asset_api.route('/api/asset/uuid/<uuid>', methods=('GET',))
def by_uuid(uuid):
    url = "{}/c/portal/truenth/asset/detailed".format(
        current_app.config["LR_ORIGIN"])
    return requests.get(url, params={'uuid': uuid}).json()['asset']
