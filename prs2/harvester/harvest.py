from __future__ import absolute_import
import arrow
import base64
from django.conf import settings
from django.core.files import File
import email
from imaplib import IMAP4_SSL
from StringIO import StringIO

from .models import EmailedReferral, EmailAttachment


class DeferredIMAP():
    '''
    Convenience class for maintaining a bit of state about an IMAP server
    and handling logins/logouts. Note that instances aren't threadsafe.
    '''
    def __init__(self, host, user, password):
        self.deletions = []
        self.flags = []
        self.host = host
        self.user = user
        self.password = password

    def login(self):
        self.imp = IMAP4_SSL(self.host)
        self.imp.login(settings.REFERRAL_EMAIL_USER, settings.REFERRAL_EMAIL_PASSWORD)
        self.imp.select("INBOX")

    def logout(self, expunge=False):
        if expunge:
            self.imp.expunge
        self.imp.close()
        self.imp.logout()

    def flush(self):
        self.login()
        if self.flags:
            #logger.info("Flagging {} unprocessable emails.".format(len(self.flags)))
            self.imp.store(",".join(self.flags), '+FLAGS', r'(\Flagged)')
        else:
            self.logout()
        self.flags, self.deletions = [], []

    def flag(self, msgid):
        self.flags.append(str(msgid))

    def __getattr__(self, name):
        def temp(*args, **kwargs):
            self.login()
            result = getattr(self.imp, name)(*args, **kwargs)
            self.logout()
            return result
        return temp


dimap = DeferredIMAP(
    host=settings.REFERRAL_EMAIL_HOST, user=settings.REFERRAL_EMAIL_USER,
    password=settings.REFERRAL_EMAIL_PASSWORD)


def retrieve_emails(search, batch_size=10):
    """Retrieve email from the IMAP server using the provided search term, e.g.
    '(FROM "referrals@planning.wa.gov.au")'
    1. Get unread emails & attachments.
    2. Mark emails as read.
    """
    #to_email = settings.REFERRAL_EMAIL_USER
    textids = dimap.search(None, search)[1][0].split(' ')
    # If no emails, just return.
    if textids == ['']:
        return []
    typ, responses = dimap.fetch(",".join(textids[-batch_size:]), '(BODY.PEEK[])')
    # If protocol error, just return.
    if typ != 'OK':
        return []
    messages = []
    for response in responses:
        if isinstance(response, tuple):
            msgid = int(response[0].split(' ')[0])
            msg = email.message_from_string(response[1])
            messages.append((msgid, msg))
    #logger.info("Fetched {}/{} messages for {}.".format(len(messages), len(textids), search))
    return messages


def harvest_emailed_referrals(emails):
    """Iterate through pass-in email messages:
    1. Per email, create a new EmailedReferral object.
    2. Per email attachment, create a new EmailAttachment object.
    """
    # TODO: logging
    for e in emails:
        uid, message = e[0], e[1]
        message_body = None
        attachments = []

        if EmailedReferral.objects.filter(email_uid=uid).exists():
            continue
        if message.is_multipart():  # Should always be True.
            parts = [i for i in message.walk()]
        else:
            continue  # TODO: log/handle this situation.

        message = parts[0]  # Redefine, for sanity.
        for p in parts[1:]:
            # First part is the multipart email - ignore it.
            # Second part is the HTML email body (probably).
            # Subsequent parts are the attachments (probably)
            if p.get_content_type() == 'text/html':
                message_body = p
            else:
                attachments.append(p)

        # Create an EmailedReferral from the email body (if found).
        if message_body:
            received = arrow.get(message.get('Received').split(';')[1].strip(), 'ddd, DD MMM YYYY hh:mm:ss Z')
            to_e = email.utils.parseaddr(message.get('To'))[1]
            from_e = email.utils.parseaddr(message.get('From'))[1]
            em_new = EmailedReferral(
                received=received.datetime, email_uid=uid, to_email=to_e,
                from_email=from_e, subject=message.get('Subject'),
                body=message_body.get_payload())
            em_new.save()
            for a in attachments:
                att_new = EmailAttachment(
                    emailed_referral=em_new, name=a.get_filename(),
                )
                data = StringIO(base64.decodestring(a.get_payload()))
                data = File(data)
                att_new.attachment.save(a.get_filename(), data)
                att_new.save()
                data.close()
