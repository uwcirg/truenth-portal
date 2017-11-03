from flask import Blueprint, make_response, render_template, request
from flask_user import roles_required
from sqlalchemy import and_

from ..extensions import oauth
from ..models.organization import Organization, UserOrganization, OrgTree
from ..models.role import ROLE
from ..models.user import User, current_user
from ..type_tools import check_int


admin = Blueprint('admin', __name__)


@admin.route('/admin')
@roles_required(ROLE.ADMIN)
@oauth.require_oauth()
def admin_index():
    """user admin view function"""
    # can't do list comprehension in template - prepopulate a 'rolelist'

    request_org_list = request.args.get('org_list', None)

    if request_org_list:
        org_list = set()

        # for selected filtered orgs, we also need to get the children
        # of each, if any
        request_org_list = set(request_org_list.split(","))
        for orgId in request_org_list:
            check_int(orgId)
            if orgId == 0:  # None of the above doesn't count
                continue
            org_list.update(OrgTree().here_and_below_id(orgId))

        users = User.query.join(UserOrganization).filter(
                    and_(UserOrganization.user_id == User.id,
                         UserOrganization.organization_id != 0,
                         UserOrganization.organization_id.in_(org_list)))
    else:
        org_list = Organization.query.all()
        users = User.query.all()

    return render_template('admin.html', users=users, wide_container="true",
                           org_list=list(org_list), user=current_user())



@admin.route('/settings', methods=['GET', 'POST'])
@roles_required(ROLE.ADMIN)
@oauth.require_oauth()
def settings():
    """settings panel for admins"""
    # load all top level orgs and consent agreements
    organization_consents = Organization.consent_agreements()

    # load all app text values - expand when possible
    apptext = {}
    for a in AppText.query.all():
        try:
            # expand strings with just config values, such as LR
            apptext[a.name] = app_text(a.name)
        except ValueError:
            # lack context to expand, show with format strings
            apptext[a.name] = a.custom_text

    form = SettingsForm(
        request.form, timeout=request.cookies.get('SS_TIMEOUT', 600))
    if not form.validate_on_submit():

        return render_template(
            'settings.html',
            form=form,
            apptext=apptext,
            organization_consents=organization_consents,
            wide_container="true")

    # make max_age outlast the browser session
    max_age = 60 * 60 * 24 * 365 * 5
    response = make_response(render_template(
        'settings.html',
        form=form,
        apptext=apptext,
        organization_consents=organization_consents,
        wide_container="true"))
    response.set_cookie('SS_TIMEOUT', str(form.timeout.data), max_age=max_age)
    return response
