from flask_mail import Mail, Connection
import smtplib
import ssl
import logging

log = logging.getLogger(__name__)

class FallbackValidatingConnection(Connection):
    def configure_host(self):
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
                    self.host.starttls(context=strict_context)

            if self.mail.username and self.mail.password:
                self.host.login(self.mail.username, self.mail.password)

            log.debug("Email: connected with strict TLS certificate validation.")

        except Exception as e:
            log.error(f"Strict TLS failed ({e}); falling back to non-validated TLS.")

            # --- Fallback: start TLS without certificate validation ---
            insecure_context = ssl._create_unverified_context()

            if self.mail.use_ssl:
                self.host = smtplib.SMTP_SSL(host, port, context=insecure_context)
            else:
                self.host = smtplib.SMTP(host, port)
                if self.mail.use_tls:
                    self.host.starttls(context=insecure_context)

            if self.mail.username and self.mail.password:
                self.host.login(self.mail.username, self.mail.password)


class FallbackValidatingMail(Mail):
    def connect(self):
        return FallbackValidatingConnection(self)
