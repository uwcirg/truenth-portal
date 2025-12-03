from flask import current_app
from flask_mail import Mail, Connection
import smtplib
import ssl


class FallbackValidatingConnection(Connection):
    def configure_host(self):
        current_app.logger.debug("FallbackValidatingConnection.configure_host()")
        current_app.logger.debug(f"use_ssl: {self.mail.use_ssl} , use_tls: {self.mail.use_tls}")
        host = self.mail.server
        port = self.mail.port

        strict_context = ssl.create_default_context()
        # Optional: load your own CA bundle
        # strict_context.load_verify_locations('my-ca.pem')

        try:
            # --- First attempt: strict certificate validation ---
            if self.mail.use_ssl:
                self.host = smtplib.SMTP_SSL(host, port, context=strict_context)
            else:
                self.host = smtplib.SMTP(host, port)
                if self.mail.use_tls:
                    current_app.logger.debug("start TLS with secure context")
                    self.host.starttls(context=strict_context)

            if self.mail.username and self.mail.password:
                current_app.logger.debug("login to mail host")
                self.host.login(self.mail.username, self.mail.password)

            current_app.logger.debug("Email: connected with strict TLS certificate validation.")

        except Exception as e:
            current_app.logger.error(f"Strict TLS failed ({e}); falling back to non-validated TLS.")

            # --- Fallback: start TLS without certificate validation ---
            insecure_context = ssl._create_unverified_context()

            if self.mail.use_ssl:
                self.host = smtplib.SMTP_SSL(host, port, context=insecure_context)
            else:
                self.host = smtplib.SMTP(host, port)
                if self.mail.use_tls:
                    current_app.logger.debug("start TLS with insecure context")
                    self.host.starttls(context=insecure_context)

            if self.mail.username and self.mail.password:
                current_app.logger.debug("login to mail host")
                self.host.login(self.mail.username, self.mail.password)


class FallbackValidatingMail(Mail):
    def init_app(self, app):
        return Mail.init_app(self, app)

    def init_mail(self, config, debug=False, testing=False):
        mail = Mail.init_mail(self, config, debug, testing)
        mail.server = config.get('MAIL_SERVER', '127.0.0.1')
        mail.username = config.get('MAIL_USERNAME')
        mail.password = config.get('MAIL_PASSWORD')
        mail.port = config.get('MAIL_PORT', 25)
        mail.use_ssl = config.get('MAIL_USE_SSL', False)
        mail.use_tls = config.get('MAIL_USE_TLS', False)
        mail.default_sender = config.get('MAIL_DEFAULT_SENDER')
        mail.debug = config.get('MAIL_DEBUG', debug)
        mail.max_emails = config.get('MAIL_MAX_EMAILS')
        mail.suppress = config.get('MAIL_SUPPRESS_SEND', testing)
        mail.ascii_attachments = config.get('MAIL_ASCII_ATTACHMENTS', False)
        return mail

    def connect(self):
        if current_app.config.get("MAIL_SERVER") and self.server is None:
            self.init_app(current_app)

        current_app.logger.debug("FallbackValidatingMail.connect()")
        current_app.logger.debug(f"server: {self.server}")
        current_app.logger.debug(f"use_ssl: {self.use_ssl} , use_tls: {self.use_tls}")
        return FallbackValidatingConnection(self)
