from flask import Blueprint, jsonify, render_template, request
from flask_user import roles_required
from sqlalchemy import and_

from ..extensions import oauth
from ..models.app_text import (
    InitialConsent_ATMA,
    MailResource,
    StaffRegistrationEmail_ATMA,
    UndefinedAppText,
    VersionedResource,
    app_text,
)
from ..models.communication import load_template_args
from ..models.organization import Organization, OrgTree, UserOrganization
from ..models.role import ROLE, Role
from ..models.user import User, UserRoles, current_user, get_user

staff = Blueprint('staff', __name__)


@staff.route('/staff-registration-email/<int:user_id>')
@roles_required([ROLE.ADMIN.value, ROLE.STAFF_ADMIN.value])
@oauth.require_oauth()
def staff_registration_email(user_id):
    """Staff Registration Email Content"""
    user = get_user(user_id, 'view')
    org = user.first_top_organization()
    args = load_template_args(user=user)

    try:
        name_key = StaffRegistrationEmail_ATMA.name_key(organization=org)
        item = MailResource(
            app_text(name_key), locale_code=user.locale_code, variables=args)
    except UndefinedAppText:
        """return no content and 204 no content status"""
        return '', 204

    return jsonify(subject=item.subject, body=item.body)


@staff.route('/staff-profile-create')
@roles_required(ROLE.STAFF_ADMIN.value)
@oauth.require_oauth()
def staff_profile_create():
    user = get_user(current_user().id, 'edit')
    consent_agreements = Organization.consent_agreements(
        locale_code=user.locale_code)

    return render_template(
        "profile/staff_profile_create.html", user=user,
        consent_agreements=consent_agreements)


@staff.route('/staff_profile/<int:user_id>')
@roles_required(ROLE.STAFF_ADMIN.value)
@oauth.require_oauth()
def staff_profile(user_id):
    """staff profile view function"""
    user = get_user(user_id, 'edit')
    consent_agreements = Organization.consent_agreements(
        locale_code=user.locale_code)
    terms = VersionedResource(
        app_text(InitialConsent_ATMA.name_key()),
        locale_code=user.locale_code)

    return render_template(
        'profile/staff_profile.html', user=user, terms=terms,
        current_user=current_user(),
        consent_agreements=consent_agreements)


@staff.route('/staff')
@roles_required(ROLE.STAFF_ADMIN.value)
@oauth.require_oauth()
def staff_index():
    """staff view function, intended for staff admin

    Present the logged in staff admin the list of staff and clinicians
    matching the staff admin's organizations (and any descendant
    organizations)

    """
    user = get_user(current_user().id, 'edit')
    ot = OrgTree()

    # empty patient query list to start, unionize with other relevant lists
    staff_list = User.query.filter(User.id == -1)

    org_list = set()
    user_orgs = set()

    # Build list of all organization ids, and their descendents, the
    # user belongs to
    for org in user.organizations:
        if org.id == 0:  # None of the above doesn't count
            continue
        org_list.update(ot.here_and_below_id(org.id))
        user_orgs.add(org.id)

    # Gather up all staff belonging to any of the orgs (and their children)
    # NOTE, a change from before, staff admin users can now edit records of
    # other users that have staff OR staff admin role(s)
    org_staff = User.query.join(UserRoles).filter(
        and_(User.id == UserRoles.user_id,
             # exclude users with admin role
             ~User.roles.any(Role.name == ROLE.ADMIN.value),
             # exclude current user from the list
             User.id != user.id)
    ).join(Role).filter(
        and_(Role.name.in_((
            ROLE.CLINICIAN.value, ROLE.STAFF.value, ROLE.STAFF_ADMIN.value)),
             UserRoles.role_id == Role.id)
    ).join(UserOrganization).filter(
        and_(UserOrganization.user_id == User.id,
             UserOrganization.organization_id.in_(org_list)))

    include_test_role = request.args.get('include_test_role')
    # not including test accounts by default, unless requested
    if not include_test_role:
        org_staff = org_staff.filter(
            ~User.roles.any(Role.name == ROLE.TEST.value))

    staff_list = staff_list.union(org_staff).all()
    return render_template(
        'admin/staff_by_org.html', staff_list=staff_list,
        user=user, wide_container="true",
        include_test_role=include_test_role)
