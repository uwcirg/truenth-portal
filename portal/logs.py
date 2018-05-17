"""SSL extension module"""
from logging.handlers import SMTPHandler


class SSLSMTPHandler(SMTPHandler):
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
            smtp = smtplib.SMTP_SSL(self.mailhost, port, timeout=self._timeout)

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
            if self.username and self.secure is not None:
                smtp.login(self.username, self.password)
            smtp.sendmail(self.fromaddr, self.toaddrs, message)
            smtp.quit()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
