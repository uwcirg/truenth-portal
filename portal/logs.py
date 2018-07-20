"""SSL extension module"""
from __future__ import unicode_literals  # isort:skip

from logging.handlers import SMTPHandler


class SSLSMTPHandler(SMTPHandler):
    """Override SMTPHandler to support SSL"""

    def __init__(
            self, username=None, password=None, mailport=None,
            use_ssl=None, **kwargs):
        """Override default to allow direct assignment of select attributes"""
        super(SSLSMTPHandler, self).__init__(**kwargs)

        for var, value in locals().items():
            if (var in ('username', 'password', 'mailport', 'use_ssl')
                    and value is not None):
                setattr(self, var, value)

    def emit(self, record):
        """
        Emit a record.
        Format the record and send it to the specified addressees.
        """
        try:
            import smtplib
            from email.utils import formatdate
            port = self.mailport
            if not port:
                port = smtplib.SMTP_PORT

            smtp_config = {
                'host': self.mailhost,
                'port': port,
                'timeout': self._timeout,
            }
            # todo: make `use_ssl` a proper attribute
            if hasattr(self, 'use_ssl') and self.use_ssl:
                smtp = smtplib.SMTP_SSL(**smtp_config)
            else:
                smtp = smtplib.SMTP(**smtp_config)

            message = '\r\n'.join((
                'From: {from_addr}',
                'To: {to_addr}',
                'Subject: {subject}',
                'Date: {date}',
                '',
                '{body}',
            )).format(
                from_addr=self.fromaddr,
                to_addr=','.join(self.toaddrs),
                subject=self.getSubject(record),
                date=formatdate(),
                body=self.format(record),
            )
            if self.username:
                smtp.login(self.username, self.password)
            smtp.sendmail(self.fromaddr, self.toaddrs, message)
            smtp.quit()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
