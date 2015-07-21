# coding: utf-8

import logging
import requests
from functools import wraps

from authomatic.extras.flask import FlaskAuthomatic
from authomatic.providers import oauth2
from datetime import datetime, timedelta
from flask import Flask, make_response
from flask import session, request, url_for
from flask import render_template, redirect, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import gen_salt
from flask_oauthlib.provider import OAuth2Provider
from sqlalchemy.dialects.postgresql import ENUM

logger = logging.getLogger('authomatic.core')
logger.addHandler(logging.StreamHandler())

app = Flask(__name__, template_folder='templates')
app.config.from_pyfile('application.cfg', silent=False)

class OAuthOrAlternateAuth(OAuth2Provider):
    """Specialize OAuth2Provider with alternate authorization"""

    def __init__(self, app=None):
        super(OAuthOrAlternateAuth, self).__init__(app)

    def require_oauth(self, *scopes):
        """Specialze the superclass decorator with alternates

        This method is intended to be in lock step with the
        super class, with the following two exceptions:

        1. if actively "TESTING", skip oauth and return
           the function, effectively undecorated.

        2. if the user appears to be locally logged in (i.e. browser
           session cookie with a valid user.id),
           return the effecively undecorated function.

        """
        def wrapper(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                # TESTING backdoor
                if app.config.get('TESTING'):
                    return f(*args, **kwargs)
                # Local login backdoor
                if current_user():
                    return f(*args, **kwargs)

                # Unmodified superclass method follows
                for func in self._before_request_funcs:
                    func()

                if hasattr(request, 'oauth') and request.oauth:
                    return f(*args, **kwargs)

                valid, req = self.verify_request(scopes)

                for func in self._after_request_funcs:
                    valid, req = func(valid, req)

                if not valid:
                    if self._invalid_response:
                        return self._invalid_response(req)
                    return abort(401)
                request.oauth = req
                return f(*args, **kwargs)
            return decorated
        return wrapper


db = SQLAlchemy(app)
oauth = OAuthOrAlternateAuth(app)

fa = FlaskAuthomatic(
    config={
        'fb': {
           'class_': oauth2.Facebook,
           'consumer_key': app.config['CONSUMER_KEY'],
           'consumer_secret': app.config['CONSUMER_SECRET'],
           'scope': ['user_about_me', 'email'],
        },
    },
    secret=app.config['SECRET_KEY'],
    debug=True,
)


# http://hl7.org/fhir/v3/AdministrativeGender/
gender_types = ENUM('male', 'female', 'undifferentiated', name='genders',
        create_type=False)


class User(db.Model):
    __tablename__ = 'users'  # Override default 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    registered = db.Column(db.DateTime, default=datetime.now)
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(40), unique=True)
    gender = db.Column('gender', gender_types)
    birthdate = db.Column(db.Date)


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
            return self._redirect_uris.split()
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
        # Chop query string and confirm it's in the list
        redirect_uri = redirect_uri.split('?')[0]
        return redirect_uri in self.redirect_uris


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

    redirect_uri = db.Column(db.String(255))
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


def current_user():
    if 'id' in session:
        uid = session['id']
        return User.query.get(uid)
    return None


@app.route('/terms-of-use')
def termsofuse():
    return render_template('termsofuse.html')


@app.route('/')
def index():
    user = current_user()
    if user:
        return render_template('portal.html', user=user)
    return render_template('index.html')


@app.route('/client', methods=('GET', 'POST'))
def client():
    user = current_user()
    if not user:
        return redirect('/')
    if request.method == 'GET':
        return render_template('register_client.html')
    redirect_uri = request.form.get('redirect_uri', None)
    item = Client(
        client_id=gen_salt(40),
        client_secret=gen_salt(50),
        _redirect_uris=redirect_uri,
        _default_scopes='email',
        user_id=user.id,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(
        client_id=item.client_id,
        client_secret=item.client_secret,
        redirect_uris=item._redirect_uris
    )


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


@app.route('/oauth/errors', methods=['GET', 'POST'])
def oauth_errors():
    return jsonify(error=request.args.get('error'))


@app.route('/oauth/token', methods=['GET', 'POST'])
@oauth.token_handler
def access_token():
    return None


@app.route('/oauth/authorize', methods=['GET', 'POST'])
@oauth.authorize_handler
def authorize(*args, **kwargs):
    user = current_user()
    if not user:
        return redirect('/')
    # Skip confirmation - return true as if user agreed to
    # let portal give API access to intervetion.
    return True


@app.route('/api/me')
@oauth.require_oauth()
def me():
    user = User.query.get(request.oauth.user.id)
    return jsonify(id=user.id, username=user.username,
            email=user.email)


@app.route('/api/demographics')
@oauth.require_oauth()
def demographics():
    """return user demographis as a FHIR patient resource (in JSON)
    
    http://www.hl7.org/fhir/patient.html
    """
    user = current_user()
    d = {}
    d['resourceType'] = "Patient"
    d['identifier'] = []
    d['identifier'].append({'label': 'Truenth identifier',
                'value': user.id})
    d['identifier'].append({'label': 'Truenth username',
                'value': user.username})
    d['name'] = {}
    if user.first_name:
        d['name']['given'] = user.first_name
    if user.last_name:
        d['name']['family'] = user.last_name
    if user.birthdate:
        d['birthDate'] = user.birthdate.strftime('%Y-%m-%d')
    d['status'] = 'registered' if user.registered else 'unknown'
    d['communication'] = 'en-US'
    d['telecom'] = []
    if user.email:
        d['telecom'].append({'system': 'email', 'value': user.email})
    if user.phone:
        d['telecom'].append({'system': 'phone', 'value': user.phone})
    return jsonify(d)


@app.route('/api/clinical')
@oauth.require_oauth()
def clinical():
    clinical_data = {
        "TNM-Condition-stage": {
            "summary": "T1 N0 M0"
        },
        "Gleason-score": "2"
    }
    return jsonify(clinical_data)


@app.route('/api/portal-wrapper-html/', defaults={'username': None})
@app.route('/api/portal-wrapper-html/<username>')
def portal_wrapper_html(username):
    html = render_template(
        'portal_wrapper.html',
        PORTAL=app.config['PORTAL'],
        username=username,
        logo_truenth=url_for(
            'static',
            filename='img/logo_truenth.png',
        ),
        logo_movember=url_for(
            'static',
            filename='img/logo_movember.png',
        ),
    )
    resp = make_response(html)
    resp.headers.add('Access-Control-Allow-Origin', '*')
    resp.headers.add('Access-Control-Allow-Headers', 'X-Requested-With')
    return resp


@app.route('/login')
@fa.login('fb')
def login():
    user = current_user()
    if user:
        return redirect('/')
    if fa.result:
        if fa.result.error:
            return fa.result.error.message
        elif fa.result.user:
            if not (fa.result.user.name and fa.result.user.id):
                fa.result.user.update()
            # Success - add or pull this user to/from portal store
            ap = AuthProvider.query.filter_by(provider='facebook',
                    provider_id=fa.result.user.id).first()
            if ap:
                user = User.query.filter_by(id=ap.user_id).first()
            else:
                # Looks like first valid login from this auth provider
                # generate what we know and redirect to get the rest
                user = User(username=fa.result.user.name,
                        first_name=fa.result.user.first_name,
                        last_name=fa.result.user.last_name,
                        birthdate=fa.result.user.birth_date,
                        gender=fa.result.user.gender,
                        email=fa.result.user.email)
                db.session.add(user)
                db.session.commit()
                ap = AuthProvider(provider='facebook',
                        provider_id=fa.result.user.id,
                        user_id=user.id)
                db.session.add(ap)
                db.session.commit()
            session['id'] = user.id
            session['remote_token'] = fa.result.provider.credentials.token
            return redirect('/')
    else:
        return fa.response


@app.route('/logout')
def logout():
    ap = AuthProvider.query.filter_by(provider='facebook',
            user_id=session['id']).first()
    headers = {'Authorization': 
            'Bearer {0}'.format(session['remote_token'])}
    url = "https://graph.facebook.com/{0}/permissions".\
        format(ap.provider_id)
    result = requests.delete(url, headers=headers)
    session.clear()
    return redirect('/')


def init_db():
    db.create_all()


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0')
