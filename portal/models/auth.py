"""Auth related model classes """
from flask import current_app
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import ENUM
from urlparse import urlparse

from ..extensions import db, oauth
from .user import current_user


providers_list = ENUM('facebook', 'twitter', 'truenth', name='providers',
                      create_type=False)


class AuthProvider(db.Model):
    __tablename__ = 'auth_providers'
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column('provider', providers_list)
    provider_id = db.Column(db.BigInteger)
    user_id = db.Column(db.ForeignKey('users.id'))
    user = db.relationship('User')


class Client(db.Model):
    __tablename__ = 'clients'  # Override default 'client'
    client_id = db.Column(db.String(40), primary_key=True)
    client_secret = db.Column(db.String(55), nullable=False)

    user_id = db.Column(db.ForeignKey('users.id'))
    user = db.relationship('User')

    _redirect_uris = db.Column(db.Text)
    _default_scopes = db.Column(db.Text)

    @property
    def client_type(self):
        return 'public'

    @property
    def redirect_uris(self):
        if self._redirect_uris:
            # Should just store the scheme:hostname:port,
            # but for now, clean here for validate_redirect_uri
            uris = [] 
            for uri in self._redirect_uris.split():
                parsed = urlparse(uri)
                uris.append('{uri.scheme}://{uri.netloc}'.format(uri=parsed))
            return uris
        return []

    @property
    def default_redirect_uri(self):
        return self.redirect_uris[0]

    @property
    def default_scopes(self):
        if self._default_scopes:
            return self._default_scopes.split()
        return []

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
            current_app.logger.warn("%s not in redirect_uris: %s",
                    redirect_uri, self.redirect_uris)
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

