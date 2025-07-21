from datetime import datetime
from urllib.parse import urlparse

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_user import roles_required
from flask_wtf import FlaskForm
from validators import url as url_validation
from werkzeug.exceptions import Unauthorized
from werkzeug.security import gen_salt
from wtforms import (
    BooleanField,
    FormField,
    HiddenField,
    SelectField,
    SelectMultipleField,
    StringField,
    validators,
    widgets,
)

from ..audit import auditable_event
from ..database import db
from ..date_tools import FHIR_datetime
from ..extensions import oauth
from ..models.auth import Token, create_service_token
from ..models.client import Client, validate_origin
from ..models.intervention import INTERVENTION, STATIC_INTERVENTIONS
from ..models.role import ROLE
from ..models.user import current_user, get_user
from .crossdomain import crossdomain

client_api = Blueprint('client', __name__)


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class InterventionEditForm(FlaskForm):
    """Intervention portion of client edits - part of ClientEditForm"""
    public_access = BooleanField('Public Access', default=True)
    card_html = StringField('Card HTML')
    link_label = StringField('Link Label')
    link_url = StringField('Link URL')
    status_text = StringField('Status Text')
    subscribed_to_user_doc_event = BooleanField(
        'POST "upload user document" event to Callback URL')

    def __init__(self, *args, **kwargs):
        """As a nested form, CSRF is handled by the parent"""
        kwargs['csrf_enabled'] = False
        super(InterventionEditForm, self).__init__(*args, **kwargs)

    def validate_link_url(form, field):
        """Custom validation to allow null and known origins only"""
        if field.data and len(field.data.strip()):
            try:
                validate_origin(field.data)
            except Unauthorized:
                raise validators.ValidationError(
                    "Invalid URL (unknown origin)")


class ClientEditForm(FlaskForm):
    """wtform class for validation during client edits"""
    intervention_names = [(k, v) for k, v in STATIC_INTERVENTIONS.items()]

    client_id = HiddenField('Client ID')
    application_role = SelectField(
        'Application Role',
        choices=intervention_names,
        validators=[validators.DataRequired()])
    application_origins = StringField(
        'Application URL',
        validators=[validators.DataRequired()])
    callback_url = StringField(
        'Callback URL',
        validators=[validators.optional(), validators.URL(require_tld=False)])
    intervention_or_default = FormField(InterventionEditForm)

    def validate_application_role(form, field):
        """Custom validation to confirm only one app per role"""
        selected = field.data
        if not selected or selected == 'None':
            return True

        # the default role isn't assigned or limited
        if selected == INTERVENTION.DEFAULT.name:
            return True

        intervention = getattr(INTERVENTION, selected)

        # if the selected intervention already has a client, make sure
        # it's the client being edited or raise a validation error
        if (intervention and intervention.client_id and
                intervention.client_id != form.data['client_id']):
            raise validators.ValidationError(
                "This role currently belongs to another application")

    def validate_application_origins(form, field):
        """Custom validation to handle multiple, space delimited URLs"""
        origins = field.data.split()
        for url in origins:
            if not url_validation(url):
                raise validators.ValidationError("Invalid URL")

    def validate_callback_url(form, field):
        """Custom validation to confirm callback_url is in redirect_urls"""
        origins = form.application_origins.data.split()
        og_uris = ['{uri.scheme}://{uri.netloc}'.format(uri=urlparse(url))
                   for url in origins]
        if field.data:
            cb_uri = urlparse(field.data)
            if '{uri.scheme}://{uri.netloc}'.format(uri=cb_uri) not in og_uris:
                raise validators.ValidationError(
                    "URL host must match a provided Application Origin URL")


@client_api.route('/client', methods=('GET', 'POST'))
@crossdomain()
@roles_required(ROLE.APPLICATION_DEVELOPER.value)
@oauth.require_oauth()
def client_reg():
    """client registration

    TrueNTH uses the OAuth 2.0 Authorization Code Grant flow
    (http://tools.ietf.org/html/rfc6749#section-4.1)
    to authorize all sensitive API access. As a prerequisite, any
    client (intervention) wishing to make authorized calls must first
    register at this endpoint.
    ---
    tags:
      - Intervention
    operationId: client
    parameters:
      - name: application_origins
        in: formData
        description:
          Application origins. The service will only redirect to URIs in
          the list. All URIs must be protected with TLS security
          (i.e. https) beyond inital testing. Separate multiple
          URIs with a single whitespace character.
        required: true
        type: string
    produces:
      - text/html
    responses:
      200:
        description: successful operation
        schema:
          id: client_response
          required:
            - App ID
            - App Secret
            - Site URL
          properties:
            App ID:
              type: string
              description:
                Identification unique to a TrueNTH application.
                Pass as `client_id` in OAuth Authorization Code Grant
                calls to obtain an authorization token
            App Secret:
              type: string
              description:
                Safe guarded secret used by Intervention's OAuth
                client library.  Pass as `client_secret` in calls
                to `/oauth/token`
            Site URL:
              type: string
              description:
                Application's site Origin(s) or URL(s).
                Required to include the origin of OAuth callbacks
                and site origins making in-browser requests via CORS
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """
    user = get_user(current_user().id, 'view')
    form = ClientEditForm(application_role=INTERVENTION.DEFAULT.name)
    if not form.validate_on_submit():
        return render_template('client_add.html', form=form)
    client = Client(
        client_id=gen_salt(40),
        client_secret=gen_salt(50),
        _redirect_uris=form.application_origins.data,
        _default_scopes='email',
        user_id=user.id,
    )
    db.session.add(client)
    db.session.commit()
    auditable_event("added intervention/client {}".format(
        client), user_id=user.id, subject_id=user.id, context='intervention')

    # if user selected a role besides the default, set it.
    if form.application_role.data != INTERVENTION.DEFAULT.name:
        selected = form.application_role.data
        intervention = getattr(INTERVENTION, selected)
        auditable_event("client {0} assuming role {1}".format(
            client.client_id, selected), user_id=user.id,
            subject_id=user.id, context='intervention')
        intervention.client_id = client.client_id
        db.session.commit()
    return redirect(url_for('.client_edit', client_id=client.client_id))


@client_api.route('/client/<client_id>', methods=('GET', 'POST'))
@crossdomain()
@roles_required(ROLE.APPLICATION_DEVELOPER.value)
@oauth.require_oauth()
def client_edit(client_id):
    """client edit

    View details and edit settings for a TrueNTH client (also
    known as an Intervention or App).
    ---
    tags:
      - Intervention
    operationId: client_edit
    parameters:
      - name: client_id
        in: path
        required: true
        description: The App ID (client_id) from client registration
        type: string
      - name: callback_url
        in: formData
        description:
          An optional callback URL to be hit on significant
          events, such as a user terminating a session via logout
        required: false
        type: string
    produces:
      - text/html
    responses:
      200:
        description: successful operation
        schema:
          id: client_edit_response
          required:
            - App ID
            - App Secret
            - Site URL
            - Callback URL
          properties:
            App ID:
              type: string
              description:
                Identification unique to a TrueNTH application.
                Pass as `client_id` in OAuth Authorization Code Grant
                calls to obtain an authorization token
            App Secret:
              type: string
              description:
                Safe guarded secret used by Intervention's OAuth
                client library.  Pass as `client_secret` in calls
                to `/oauth/token`
            Site URL:
              type: string
              description:
                Application's site Origin or URL.
                Required to include the origin of OAuth callbacks
                and site origins making in-browser requests via CORS
            Callback URL:
              type: string
              description:
                Callback URL hit on significant events such as a
                session termination.  If defined, a POST to the
                callback will include a "signed_request" using
                the client_secret.  See numerous resources
                published for decoding Facebook signed_request, as
                the format is identical.
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []
    """
    client = Client.query.get(client_id)
    if not client:
        abort(404)
    user = get_user(current_user().id, 'view')
    get_user(client.user_id, 'edit')  # confirm auth

    if request.method == 'POST':
        form = ClientEditForm(request.form)
    else:
        form = ClientEditForm(
            obj=client,
            application_role=client.intervention_or_default.name)

    # work around a testing bug in wtforms
    if current_app.config['TESTING']:
        form.client_id.data = client_id
    if form.client_id.data != client_id:
        raise RuntimeError("Form client doesn't match argument")

    def set_client_intervention(client, form):
        current_role = client.intervention
        selected = form.application_role.data
        if current_role and current_role.name != selected:
            current_role.client_id = None
            auditable_event("client {0} releasing role {1}".format(
                client.client_id, current_role.description),
                user_id=user.id, subject_id=client.user_id,
                context='intervention')
        if selected != INTERVENTION.DEFAULT.name:
            intervention = getattr(INTERVENTION, selected)
            if intervention.client_id != client.client_id:
                intervention.client_id = client.client_id
                auditable_event("client {0} assuming role {1}".format(
                    client.client_id, intervention.description),
                    user_id=user.id, subject_id=client.user_id,
                    context='intervention')

    def generate_callback(client):
        # Trigger a callback for client editors to test
        data = {
            'event': 'test callback',
            'UTC server time': FHIR_datetime.as_fhir(datetime.utcnow())
        }
        client.notify(data)

    if not form.validate_on_submit():
        return render_template(
            'client_edit.html', client=client, form=form,
            service_token=client.lookup_service_token())

    b4 = str(client)
    redirect_target = url_for('.clients_list')
    if request.form.get('delete'):
        auditable_event("deleted intervention/client {}".format(
            client.client_id), user_id=user.id, subject_id=client.user_id,
            context='intervention')
        if client.intervention:
            client.intervention.client_id = None
        tokens = Token.query.filter(Token.client_id == client_id)
        for t in tokens:
            db.session.delete(t)
        db.session.delete(client)
    elif request.form.get('service_token'):
        # limiting this to the client owner as sponsorship gets messy
        if user.id != client.user_id:
            raise ValueError("only client owner can add service accounts")
        existing = client.lookup_service_token()
        if existing:
            db.session.delete(existing)
        service_user = user.add_service_account()
        auditable_event(
            "service account created by {}".format(user.display_name),
            user_id=user.id, subject_id=client.user_id,
            context='authentication')
        create_service_token(client=client, user=service_user)
        auditable_event("service token generated for client {}".format(
            client.client_id), user_id=user.id, subject_id=client.user_id,
            context='authentication')
        redirect_target = url_for('.client_edit', client_id=client.client_id)
    elif request.form.get('generate_callback'):
        generate_callback(client)
        redirect_target = url_for('.client_edit', client_id=client.client_id)
    else:
        form.populate_obj(client)
        set_client_intervention(client, form)

    db.session.commit()
    after = str(client)
    if b4 != after:
        auditable_event(
            "edited intervention/client {} before: <{}> after: <{}>".format(
                client.client_id, b4, after), user_id=user.id,
            subject_id=client.user_id, context='intervention')
    return redirect(redirect_target)


@client_api.route('/clients')
@crossdomain()
@roles_required([ROLE.APPLICATION_DEVELOPER.value, ROLE.ADMIN.value])
@oauth.require_oauth()
def clients_list():
    """clients list

    List all clients created by the authenticated user.
    ---
    tags:
      - Intervention
    operationId: clients_list
    produces:
      - text/html
    responses:
      200:
        description: successful operation
        schema:
          id: clients_list_response
          required:
            - App ID
            - Site URL
          properties:
            App ID:
              type: string
              description:
                Identification unique to a TrueNTH application.
                Pass as `client_id` in OAuth Authorization Code Grant
                calls to obtain an authorization token
            Site URL:
              type: string
              description:
                Application's site Origin or URL.
                Required to include the origin of OAuth callbacks
                and site origins making in-browser requests via CORS
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """
    user = get_user(current_user().id, 'view')
    if user.has_role(ROLE.ADMIN.value):
        clients = Client.query.all()
    else:
        clients = Client.query.filter_by(user_id=user.id).all()
    return render_template('clients_list.html', clients=clients)
