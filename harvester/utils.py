import base64
import logging
from datetime import date, datetime
from email import message_from_bytes
from email.message import EmailMessage
from email.policy import default
from email.utils import getaddresses, parseaddr, parsedate
from imaplib import IMAP4_SSL
from ssl import SSLEOFError
from typing import Any, Literal
from zoneinfo import ZoneInfo

import requests
from dbca_utils.utils import env
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from lxml.html import fromstring
from lxml_html_clean import clean_html

LOGGER: logging.Logger = logging.getLogger("harvester")
UTC: ZoneInfo = ZoneInfo("UTC")


def get_imap(mailbox: str = "INBOX") -> IMAP4_SSL | Literal[False]:
    """Instantiate a new IMAP object, login, and connect to a mailbox."""
    try:
        imap = IMAP4_SSL(settings.REFERRAL_EMAIL_HOST)
        imap.login(settings.REFERRAL_EMAIL_USER, settings.REFERRAL_EMAIL_PASSWORD)
        imap.select(mailbox)
        return imap
    except (IMAP4_SSL.abort, IMAP4_SSL.error, SSLEOFError) as err:
        LOGGER.warning(f"Unable to log into mailbox: {err}")
        return False


def email_get_unread(imap: IMAP4_SSL, from_email: str) -> tuple[str, list] | tuple[Literal[False], Literal[False]]:
    """Returns (status, [list of UIDs]) of unread emails."""
    try:
        status, response = imap.uid("SEARCH", f'(UNSEEN FROM "{from_email}" UNFLAGGED)')
    except (IMAP4_SSL.abort, IMAP4_SSL.error) as err:
        LOGGER.warning(f"Unable to search unread emails from {from_email}: {err}")
        return False, False

    if status != "OK":
        return status, response

    return status, response[0].split() if response and response[0] else []


def normalise_imap_uid(value: str | bytes | int | None) -> str | None:
    """Return a valid IMAP UID string, or None when the value is unusable."""
    if value is None:
        return None

    if isinstance(value, bytes):
        value = value.decode("ascii", errors="ignore")
    elif isinstance(value, int):
        value = str(value)

    value = str(value).strip()
    if not value or value == "0":
        return None

    try:
        int(value)
    except ValueError:
        return None

    return value


def email_fetch(imap: IMAP4_SSL, uid: str) -> tuple[str, EmailMessage] | tuple[Literal[False], Literal[False]]:
    """Fetch a single email and return a tuple of status, EmailMessage."""
    uid_value = normalise_imap_uid(uid)
    if not uid_value:
        LOGGER.warning(f"Unable to fetch email: invalid message UID {uid!r}")
        return False, False

    try:
        status, msg_data = imap.uid("FETCH", uid_value, "(RFC822)")
    except (IMAP4_SSL.abort, IMAP4_SSL.error) as err:
        LOGGER.warning(f"Unable to fetch email: {err}")
        return False, False

    if status != "OK" or not msg_data or msg_data[0] is None:
        return False, False

    raw_email = msg_data[0][1]
    if not isinstance(raw_email, bytes):
        return False, False

    email_msg = message_from_bytes(s=raw_email, policy=default)

    return status, email_msg


def harvest_email(uid: int | bytes | str, message: Any) -> bool:
    """Harvest a passed-in UID and email message.
    Abort if UID exists in the database already.
    """
    from .models import EmailAttachment, EmailedReferral

    if message and message.is_multipart():  # Should always be True.
        parts = [i for i in message.walk()]
    else:
        LOGGER.warning(f"Email UID {uid} is not of type multipart")
        return False

    message_body = None
    attachments = []

    for part in parts:
        # 'text/html' or 'text/plain' content should be the email body.
        if part.get_content_type() in ["text/html", "text/plain"]:
            message_body = part
        # Other content types (not multipart/mixed) are attachments (normally application/octet-stream).
        elif part.get_content_type() != "multipart/mixed":
            attachments.append(part)

    # Create & return EmailedReferral from the email body (if found).
    if message_body:
        try:
            # The "To" or "CC" address might very well be a list of recipients.
            # We'll check them against the list in settings.ASSESSOR_EMAILS,
            # and use the first of those we match with.
            to_emails = message.get("To")  # Might be None.
            if not to_emails:  # Recipient(s) might be CC'd instead.
                to_emails = message.get("CC")
            if not to_emails:  # Still might be no recipient(s) if we've been BCC'd.
                to_emails = ""

            to_e = "BCC"
            if to_emails:
                for _, email_address in getaddresses([to_emails]):
                    if not email_address:
                        continue
                    email_address = email_address.lower()
                    if email_address in settings.ASSESSOR_EMAILS:
                        to_e = email_address
                        break

            from_e = parseaddr(message.get("From"))[1]
            # Parse the 'sent' date & time (assume UTC from the server).
            d = parsedate(message.get("Date"))
            # Returns a tuple, but we only want part of it.
            if d:
                d = d[0:6]
                dt = datetime(*d, tzinfo=UTC)  # Construct datetime from the tuple.
            else:
                dt = timezone.now()
            received = dt.astimezone(settings.TZ)
            # Generate an EmailedReferral object.
            em_new = EmailedReferral(
                received=received,
                email_uid=str(uid),
                to_email=to_e,
                from_email=from_e,
                subject=message.get("Subject"),
            )
            if message_body.get_content_type() == "text/html":
                # Strip the HTML from the message body and just save the text content.
                t = fromstring(clean_html(message_body.get_payload()))
                em_new.body = t.text_content().replace("=\n", "").strip()
            else:
                em_new.body = message_body.get_payload()  # Plain text body.
            em_new.save()
            LOGGER.info(f"Email UID {uid} harvested: {em_new.subject}")
            for a in attachments:
                att_name = a.get_filename()
                att_new = EmailAttachment(emailed_referral=em_new, name=att_name)
                try:
                    data = a.get_payload(decode=True)
                except Exception:
                    payload = a.get_payload()
                    if isinstance(payload, str):
                        data = base64.b64decode(payload, validate=False)
                    else:
                        data = payload
                if data is None:
                    continue
                if att_name and data:  # Some attachments may have no payload.
                    new_file = ContentFile(data)
                    att_new.attachment.save(att_name, new_file)
                    att_new.save()
                    LOGGER.info(f"Email attachment created: {att_new.name}")
        except Exception:
            LOGGER.exception(f"Email UID {uid} generated exception during harvest")
            return False
    else:
        LOGGER.error(f"Email UID {uid} had no message body")
        return False

    return True


def email_mark_read(imap: IMAP4_SSL, uid: str) -> tuple[str, list[Any]] | tuple[Literal[False], Literal[False]]:
    """Flag an email as 'Seen' based on passed-in UID."""
    uid_value = normalise_imap_uid(uid)
    if not uid_value:
        return False, False

    try:
        status, response = imap.uid("STORE", uid_value, "+FLAGS", r"(\Seen)")
        return status, response
    except (IMAP4_SSL.abort, IMAP4_SSL.error) as err:
        LOGGER.warning(f"Unable to mark email read: {err}")
        return False, False


def email_mark_unread(imap: IMAP4_SSL, uid: str) -> tuple[str, list[Any]] | tuple[Literal[False], Literal[False]]:
    """Remove the 'Seen' flag from an email based on passed-in UID."""
    uid_value = normalise_imap_uid(uid)
    if not uid_value:
        return False, False

    try:
        status, response = imap.uid("STORE", uid_value, "-FLAGS", r"(\Seen)")
        return status, response
    except (IMAP4_SSL.abort, IMAP4_SSL.error) as err:
        LOGGER.warning(f"Unable to mark email unread: {err}")
        return False, False


def email_mark_deleted(imap: IMAP4_SSL, uid: str) -> tuple[str, list[Any]] | tuple[Literal[False], Literal[False]]:
    """Flag an email for deletion based on the passed-in UID."""
    uid_value = normalise_imap_uid(uid)
    if not uid_value:
        return False, False

    try:
        status, response = imap.uid("STORE", uid_value, "+FLAGS", r"(\Deleted)")
        return status, response
    except (IMAP4_SSL.abort, IMAP4_SSL.error) as err:
        LOGGER.warning(f"Unable to delete email: {err}")
        return False, False


def harvest_unread_emails(from_email: str, purge_email: bool = False) -> list[str] | Literal[False]:
    """Download a list of unread email from the specified email address and
    harvest each one. Optionally purge harvested emails on completion.
    """
    LOGGER.info(f"Requesting unread emails from {from_email}")

    imap = get_imap()
    if not imap:
        LOGGER.warning("IMAP connection error")
        return False

    actions: list[str] = []
    actions.append(f"{timezone.now().isoformat()} Requesting unread emails from {from_email}")
    status, uids = email_get_unread(imap, from_email)

    if status != "OK":
        LOGGER.error(f"Server response failure: {status}")
        actions.append(f"{timezone.now().isoformat()} Server response failure: {status}")
        return actions

    if not uids:
        return actions

    LOGGER.info(f"Server lists {len(uids)} unread emails from {from_email}")
    actions.append(f"{timezone.now().isoformat()} Server lists {len(uids)} unread emails")

    if uids:
        for uid in uids:
            # Decode uid to a string if required.
            if isinstance(uid, bytes):
                uid = uid.decode("utf-8")

            # Fetch email message.
            LOGGER.info(f"Fetching email UID {uid}")
            status, message = email_fetch(imap, uid)
            if status != "OK":
                LOGGER.error(f"Server response failure on fetching email UID {uid}: {status}")
                continue
            LOGGER.info(f"Harvesting email UID {uid}")
            actions.append(f"{timezone.now().isoformat()} Harvesting email UID {uid}")
            harvest_email(uid, message)

            # Optionally mark email as read and flag it for deletion.
            if purge_email:
                # Mark email as read.
                status, _ = email_mark_read(imap, uid)
                if status == "OK":
                    LOGGER.info(f'Email UID {uid} was marked as "Read"')
                # Mark email for deletion.
                status, _ = email_mark_deleted(imap, uid)
                if status == "OK":
                    LOGGER.info(f"Email UID {uid} was marked for deletion")

        LOGGER.info(f"Harvest process completed ({from_email})")
        actions.append(f"{timezone.now().isoformat()} Harvest process completed ({from_email})")

    imap.expunge()
    imap.logout()
    return actions


def import_harvested_refs() -> list[str]:
    """Process harvested referrals and generate referrals & records within PRS"""
    from .models import EmailedReferral

    actions: list[str] = []
    LOGGER.info("Starting import of harvested referrals")
    actions.append(f"{timezone.now().isoformat()} Starting import of harvested referrals")
    # Process harvested refs that are unprocessed at present.
    for er in EmailedReferral.objects.filter(referral__isnull=True, processed=False):
        actions += er.harvest()

    LOGGER.info("Import process completed")
    actions.append(f"{timezone.now().isoformat()} Import process completed")
    return actions


def email_harvest_actions(to_emails: list[str], actions: list[str]) -> None:
    """Function to email a log of harvest actions to users.
    Accepts a list of emails and list of actions to append.
    """
    ts: str = date.today().strftime("%x")
    subject = f"PRS emailed referral harvest log {ts}"
    from_email = "PRS-Alerts@dbca.wa.gov.au"
    text_content = """This is an automated message to summarise harvest
    actions undertaken for emailed referrals.\n
    Actions:\n"""
    html_content = """<p>This is an automated message to summarise harvest
    actions undertaken for emailed referrals.</p>
    <p>Actions:</p>"""
    for action in actions:
        text_content += f"{action}\n"
        html_content += f"{action}<br>"
    msg = EmailMultiAlternatives(subject, text_content, from_email, to_emails)
    msg.attach_alternative(html_content, "text/html")
    # Email should fail gracefully (no Exception raised on failure).
    msg.send(fail_silently=True)


def query_slip(pin: int | str) -> requests.Response:
    """Function to query the Landgate SLIP service for a cadastral location, by PIN.
    DEPRECATED - use query_slip_esri instead.
    """
    url = env("SLIP_WFS_URL", None)
    auth = (env("SLIP_USERNAME", None), env("SLIP_PASSWORD", None))
    type_name = env("SLIP_DATASET", "")
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "typeName": type_name,
        "request": "getFeature",
        "outputFormat": "json",
        "cql_filter": f"polygon_number={pin}",
    }
    resp: requests.Response = requests.get(url, auth=auth, params=params, timeout=settings.HTTP_TIMEOUT)
    return resp


def query_slip_esri(pin: int | str) -> dict[str, Any]:
    """Function to query the Landgate SLIP service (Esri REST API) for a cadastral location, by PIN.
    Ref: https://catalogue.data.wa.gov.au/group/about/cadastre
    """
    url = env("SLIP_ESRI_FS_URL", None)
    url = url + "/query"  # Add query suffix to the URL.
    auth = (env("SLIP_USERNAME", None), env("SLIP_PASSWORD", None))
    params = {
        "f": "json",
        "outSR": 4326,
        "outFields": "*",
        "returnGeometry": "true",
        "where": f"polygon_number={pin}",
    }
    resp: requests.Response = requests.get(url, auth=auth, params=params, timeout=settings.HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()
