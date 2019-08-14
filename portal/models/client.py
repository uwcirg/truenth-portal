import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlparse

from flask import abort, current_app

from ..database import db
from ..extensions import oauth
from ..factories.celery import create_celery
from .auth import Token
from .intervention import Intervention, UserIntervention
from .relationship import RELATIONSHIP


class Client(db.Model):
    __tablename__ = 'clients'  # Override default 'client'
    client_id = db.Column(db.String(40), primary_key=True)
    client_secret = db.Column(db.String(55), nullable=False)

    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User')

    _redirect_uris = db.Column(db.Text)
    _default_scopes = db.Column(db.Text)
    callback_url = db.Column(db.Text)

    intervention = db.relationship(
        'Intervention',
        primaryjoin="Client.client_id==Intervention.client_id",
        uselist=False, backref='Intervention')

    grants = db.relationship('Grant', cascade='delete')

    @property
    def intervention_or_default(self):
        """To use the WTForm classes, always need a live intervention

        if there isn't an intervention assigned to this client, return
        the default

        """
        from .intervention import INTERVENTION
        if self.intervention:
            return self.intervention
        return INTERVENTION.DEFAULT

    def __str__(self):
        """print details needed in audit logs"""
        return "Client: {0}, redirects: {1}, callback: {2} {3}".format(
            self.client_id, self._redirect_uris, self.callback_url,
            self.intervention_or_default)

    @property
    def redirect_uris(self):
        if self._redirect_uris:
            # OAuth 2 spec requires a full path to the authorize URL
            # but in practice, this is too high of a bar (at least for
            # Liferay).  Only comparing by origin (scheme:hostname:port)
            # in validate_redirect_uri - so that's all we return

            # Whitelist any redirects to shared services
            uris = [
                "https://%s" % current_app.config['SERVER_NAME'],
                "http://%s" % current_app.config['SERVER_NAME'],
            ]
            for uri in self._redirect_uris.split():
                parsed = urlparse(uri)
                uris.append('{uri.scheme}://{uri.netloc}'.format(uri=parsed))
            return uris
        return []

    @property
    def application_origins(self):
        """One or more application origins, white space delimited"""
        return self._redirect_uris

    @application_origins.setter
    def application_origins(self, values):
        """Set application origins, single string of space delimited URLs"""
        self._redirect_uris = values

    def as_json(self):
        """serialize the client"""
        d = {'resourceType': 'Client'}
        for attr in (
                'client_id', 'client_secret', '_redirect_uris',
                'callback_url', 'user_id'):
            if getattr(self, attr, None) is not None:
                d[attr] = getattr(self, attr)

        return d

    @property
    def default_redirect_uri(self):
        return self.redirect_uris[0]

    @property
    def default_scopes(self):
        if self._default_scopes:
            return self._default_scopes.split()
        return []

    @classmethod
    def from_json(cls, data):
        client = cls()
        return client.update_from_json(data)

    def update_from_json(self, data):
        if 'client_id' not in data:
            raise ValueError("required 'client_id' field not found")

        for attr in (
                'client_id', 'client_secret', '_redirect_uris',
                'callback_url', 'user_id'):
            setattr(self, attr, data.get(attr))

        return self

    def notify(self, data):
        """POST data to client's callback_url if defined

        Clients can register a callback URL.  Events such as
        logout are then reported to the client via POST.

        A "signed_request" is POSTed, of the following form
           encoded_signature.payload

        The "payload" is a base64 url encoded string.
        The "encoded signature" is a HMAC_SHA256 hash using
        the client's secret key to encode the payload.

        Data should be a dictionary.  Additional fields (algorithm,
        issued_at) will be added before transmission.

        """
        if not self.callback_url:
            return

        data['algorithm'] = 'HMAC-SHA256'
        data['issued_at'] = int(time.time())
        b64payload = base64.urlsafe_b64encode(json.dumps(data).encode('utf-8'))
        sig = hmac.new(
            key=self.client_secret.encode('utf-8'),
            msg=b64payload,
            digestmod=hashlib.sha256,
        ).digest()
        b64sig = base64.urlsafe_b64encode(sig)

        formdata = {
            'signed_request': "{0}.{1}".format(b64sig, b64payload)}
        current_app.logger.debug(
            "POSTing {} event to {}".format(data['event'], self.callback_url))

        # Use celery asynchronous task 'post_request'
        kwargs = {'url': self.callback_url, 'data': formdata}
        celery = create_celery(current_app)

        res = celery.send_task('tasks.post_request', kwargs=kwargs)

        context = {
            "id": res.task_id,
            "url": self.callback_url,
            "formdata": formdata,
            "data": data,
        }
        current_app.logger.debug(str(context))

    def lookup_service_token(self):
        sponsor_relationship = [
            r for r in self.user.relationships if
            r.relationship.name == RELATIONSHIP.SPONSOR.value]
        if sponsor_relationship:
            if len(sponsor_relationship) != 1:
                raise ValueError(
                    "Expecting exactly one owner:sponsor for service token")
            return Token.query.filter_by(
                client_id=self.client_id,
                user_id=sponsor_relationship[0].other_user_id).first()
        return None

    def validate_redirect_uri(self, redirect_uri):
        """Validate the redirect_uri from the OAuth Token request

        The RFC requires exact match on the redirect_uri.  In practice
        this is too great of a burden for the interventions.  Make
        sure it's from the same scheme:://host:port the client
        registered with

        http://tools.ietf.org/html/rfc6749#section-4.1.3

        """
        parsed = urlparse(redirect_uri)
        redirect_uri = '{uri.scheme}://{uri.netloc}'.format(uri=parsed)
        if redirect_uri not in self.redirect_uris:
            return False
        return True


@oauth.clientgetter
def load_client(client_id):
    return Client.query.filter_by(client_id=client_id).first()


def client_event_dispatch(event, user, **kwargs):
    """Dispatch event data to interested clients

    Client applications register for certain events, such as logout
    or user_document uploads.  This dispatches the event to the appropriate
    clients.

    NB the determination of which clients to notify is a combination of
    interventions subscribed to the matching event, and a function of valid
    token types for the event.  For example, on logout, alert the
    client interventions owning a token for the user.  For document uploads,
    rely only on a valid callback URL, as the user may not have logged
    into the subscribed intervention.

    :param event: occurring event to dispatch
    :param user: subject user behind event
    :param kwargs: any additional data to be bundled and sent to client

    """
    data = kwargs
    data.update({"event": event, "user_id": user.id})

    if event == 'logout':
        # Look for tokens this user obtained, notify the respective clients
        # of the logout event and invalidate all outstanding tokens by deletion
        for token in Token.query.filter_by(user_id=user.id):
            c = Client.query.filter_by(client_id=token.client_id).first()
            # If the client is associated with an intervention, respect
            # subscription bit
            if not c.intervention or c.intervention.subscribed_to_logout_event:
                # Include the refresh_token when available  as some clients
                # use to uniquely identify session.
                data['refresh_token'] = token.refresh_token
                c.notify(data)
            # Invalidate the access token by deletion
            db.session.delete(token)
        db.session.commit()
    elif event == 'user_document_upload':
        # Inform interventions subscribed to this event, if there's a
        # matching row for the (user, intervention), with specific
        # access of `granted` or `subscribed`.
        for intervention in Intervention.query.filter(
                Intervention.name != 'default'):
            if intervention.subscribed_to_user_doc_event:
                ui = UserIntervention.query.filter(
                    UserIntervention.intervention_id ==
                    intervention.id).filter(
                    UserIntervention.user_id == user.id).first()
                if ui and ui.access in ('granted', 'subscribed'):
                    intervention.client.notify(data)
    else:
        raise ValueError("Unexpected event: {}".format(event))


def validate_origin(origin):
    """Validate the origin is one we recognize

    For CORS, limit the requesting origin to the list we know about,
    namely any origins belonging to our OAuth clients, or the local server

    :raises :py:exc:`werkzeug.exceptions.Unauthorized`: if we don't
      find a match.

    """
    if not origin:
        current_app.logger.warning("Can't validate missing origin")
        abort(401, "Can't validate missing origin")

    po = urlparse(origin)
    if po.netloc and (
        po.netloc == current_app.config.get("SERVER_NAME") or
        po.netloc in current_app.config.get("CORS_WHITELIST")
    ):
        return True

    if not po.scheme and not po.netloc and po.path:
        return True

    for client in Client.query.all():
        if client.validate_redirect_uri(origin):
            return True

    current_app.logger.warning("Failed to validate origin: %s", origin)
    abort(401, "Failed to validate origin %s" % origin)
