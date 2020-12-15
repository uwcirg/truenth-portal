import os

from flask_session import Session, RedisSessionInterface
from flask_session.sessions import total_seconds


class BaseRedisSessionInterface(RedisSessionInterface):
    """Override RedisSessionInterface save_session() method to passthrough flask config"""

    def save_session(self, app, session, response):
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        if not session:
            if session.modified:
                self.redis.delete(self.key_prefix + session.sid)
                response.delete_cookie(
                    app.session_cookie_name,
                    domain=domain,
                    path=path,
                )
            return

        # Modification case.  There are upsides and downsides to
        # emitting a set-cookie header each request.  The behavior
        # is controlled by the :meth:`should_set_cookie` method
        # which performs a quick check to figure out if the cookie
        # should be set or not.  This is controlled by the
        # SESSION_REFRESH_EACH_REQUEST config flag as well as
        # the permanent flag on the session itself.
        # if not self.should_set_cookie(app, session):
        #    return

        httponly = self.get_cookie_httponly(app)
        secure = self.get_cookie_secure(app)
        # call new flask config method for reading configured sameSite cookie value
        samesite = self.get_cookie_samesite(app)
        expires = self.get_expiration_time(app, session)
        val = self.serializer.dumps(dict(session))
        self.redis.setex(
            name=self.key_prefix + session.sid, value=val,
            time=total_seconds(app.permanent_session_lifetime),
        )
        if self.use_signer:
            session_id = self._get_signer(app).sign(want_bytes(session.sid))
        else:
            session_id = session.sid

        response.set_cookie(
            app.session_cookie_name,
            session_id,
            expires=expires,
            httponly=httponly,
            domain=domain,
            path=path,
            secure=secure,
            samesite=samesite,
        )


class RedisSameSiteSession(Session):
    """Extends flask-session to passthrough SESSION_COOKIE_SAMESITE flask config"""
    def _get_interface(self, app):
        config = app.config.copy()
        config.setdefault('SESSION_TYPE', 'null')
        config.setdefault('SESSION_PERMANENT', True)
        config.setdefault('SESSION_USE_SIGNER', False)
        config.setdefault('SESSION_KEY_PREFIX', 'session:')
        config.setdefault('SESSION_REDIS', None)
        session_interface = BaseRedisSessionInterface(
            config['SESSION_REDIS'],
            config['SESSION_KEY_PREFIX'],
            config['SESSION_USE_SIGNER'],
            config['SESSION_PERMANENT'],
        )
        return session_interface
