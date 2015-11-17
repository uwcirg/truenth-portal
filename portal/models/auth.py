"""Auth related model classes """
import base64
import hashlib
import hmac
import json
import requests
import time
from flask import abort, current_app
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import ENUM
from urlparse import urlparse

from ..extensions import db, oauth
from ..tasks import post_request
from .user import current_user


providers_list = ENUM('facebook', 'google', 'twitter', 'truenth',
        name='providers', create_type=False)


class AuthProvider(db.Model):
    __tablename__ = 'auth_providers'
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column('provider', providers_list)
    provider_id = db.Column(db.String(40))
    user_id = db.Column(db.ForeignKey('users.id', ondelete='CASCADE'))
    user = db.relationship('User')


class Client(db.Model):
    __tablename__ = 'clients'  # Override default 'client'
    client_id = db.Column(db.String(40), primary_key=True)
    client_secret = db.Column(db.String(55), nullable=False)

    user_id = db.Column(db.ForeignKey('users.id'))
    user = db.relationship('User')

    _redirect_uris = db.Column(db.Text)
    _default_scopes = db.Column(db.Text)
    callback_url = db.Column(db.Text)

    @property
    def client_type(self):
        return 'public'

    @property
    def redirect_uris(self):
        if self._redirect_uris:
            # OAuth 2 spec requires a full path to the authorize URL
            # but in practice, this is too high of a bar (at least for
            # Liferay).  Only comparing by origin (scheme:hostname:port)
            # in validate_redirect_uri - so that's all we return
            uris = []
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
        "Set application origins, single string of space delimited URLs"
        self._redirect_uris = values

    @property
    def default_redirect_uri(self):
        return self.redirect_uris[0]

    @property
    def default_scopes(self):
        if self._default_scopes:
            return self._default_scopes.split()
        return []

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
        payload = base64.urlsafe_b64encode(json.dumps(data))
        sig = hmac.new(str(self.client_secret), msg=payload,
            digestmod=hashlib.sha256).digest()
        encoded_sig = base64.urlsafe_b64encode(sig)

        formdata = {'signed_request': "{0}.{1}".format(encoded_sig,
            payload)}
        current_app.logger.debug("POSTing event to %s",
                self.callback_url)

        # Use celery asynchronous task 'post_request'
        kwargs = {'url': self.callback_url, 'data': formdata}
        res = post_request.apply_async(kwargs=kwargs)
        context = {"id": res.task_id, "url": kwargs['url'],
                "data": kwargs['data']}
        current_app.logger.debug(str(context))


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


class Grant(db.Model):
    __tablename__ = 'grants'  # Override default 'grant'
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='CASCADE')
    )
    user = db.relationship('User')

    client_id = db.Column(
        db.String(40), db.ForeignKey('clients.client_id'),
        nullable=False,
    )
    client = db.relationship('Client')

    code = db.Column(db.String(255), index=True, nullable=False)

    redirect_uri = db.Column(db.Text)
    expires = db.Column(db.DateTime)

    _scopes = db.Column(db.Text)

    def delete(self):
        db.session.delete(self)
        db.session.commit()
        return self

    @property
    def scopes(self):
        if self._scopes:
            return self._scopes.split()
        return []

    def validate_redirect_uri(self, redirect_uri):
        """Validate the redirect_uri from the OAuth Grant request

        The RFC requires exact match on the redirect_uri.  In practice
        this is too great of a burden for the interventions.  Make
        sure it's from the same scheme:://host:port the client
        registered with

        http://tools.ietf.org/html/rfc6749#section-4.1.3

        """
        # Use same implementation found in client
        return self.client.validate_redirect_uri(redirect_uri)


class Token(db.Model):
    __tablename__ = 'tokens'  # Override default 'token'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(
        db.String(40), db.ForeignKey('clients.client_id'),
        nullable=False,
    )
    client = db.relationship('Client')

    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id')
    )
    user = db.relationship('User')

    # currently only bearer is supported
    token_type = db.Column(db.String(40))

    access_token = db.Column(db.String(255), unique=True)
    refresh_token = db.Column(db.String(255), unique=True)
    expires = db.Column(db.DateTime)
    _scopes = db.Column(db.Text)

    @property
    def scopes(self):
        if self._scopes:
            return self._scopes.split()
        return []

@oauth.clientgetter
def load_client(client_id):
    return Client.query.filter_by(client_id=client_id).first()


@oauth.grantgetter
def load_grant(client_id, code):
    return Grant.query.filter_by(client_id=client_id, code=code).first()


@oauth.grantsetter
def save_grant(client_id, code, request, *args, **kwargs):
    # decide the expires time yourself
    expires = datetime.utcnow() + timedelta(seconds=100)
    grant = Grant(
        client_id=client_id,
        code=code['code'],
        redirect_uri=request.redirect_uri,
        _scopes=' '.join(request.scopes),
        user=current_user(),
        expires=expires
    )
    db.session.add(grant)
    db.session.commit()
    return grant


@oauth.tokengetter
def load_token(access_token=None, refresh_token=None):
    if access_token:
        return Token.query.filter_by(access_token=access_token).first()
    elif refresh_token:
        return Token.query.filter_by(refresh_token=refresh_token).first()


@oauth.tokensetter
def save_token(token, request, *args, **kwargs):
    toks = Token.query.filter_by(
        client_id=request.client.client_id,
        user_id=request.user.id
    )
    # make sure that every client has only one token connected to a user
    for t in toks:
        db.session.delete(t)

    expires_in = token.get('expires_in')
    expires = datetime.utcnow() + timedelta(seconds=expires_in)

    tok = Token(
        access_token=token['access_token'],
        refresh_token=token['refresh_token'],
        token_type=token['token_type'],
        _scopes=token['scope'],
        expires=expires,
        client_id=request.client.client_id,
        user_id=request.user.id,
    )
    db.session.add(tok)
    db.session.commit()
    return tok


def validate_client_origin(origin):
    """Validate the origin is one we recognize

    For CORS, limit the requesting origin to the list we know about,
    namely any origins belonging to our OAuth clients.

    @raises: 401 if we don't find a match.

    """
    if not origin:
        current_app.logger.error("Can't validate missing origin")
        abort(401)

    for client in Client.query.all():
        if client.validate_redirect_uri(origin):
            return True
    current_app.logger.error("Failed to validate origin: %s", origin)
    abort(401)
