from django.conf import settings
import docx2txt
from extract_msg import Message
import pdfminer
import typesense
from referral.models import Referral, Record


def typesense_client():
    """Return a typesense Client object for accessing document collections.
    """
    client = typesense.Client({
        'nodes': [{
            'host': settings.TYPESENSE_HOST,
            'port': settings.TYPESENSE_PORT,
            'protocol': settings.TYPESENSE_PROTOCOL,
        }],
        'api_key': settings.TYPESENSE_API_KEY,
        'connection_timeout_seconds': 2
    })
    return client


def typesense_index_referrals(client, qs=None):
    """Index the passed-in queryset of referrals, or all of them.
    """
    if not qs:
        qs = Referral.objects.current()
    for ref in qs:
        ref_document = {
            'referral_id': ref.pk,
            'type': ref.type.name,
            'referring_org': ref.referring_org.name,
            'referral_year': ref.referral_date.year,
            'regions': [i.name for i in ref.regions.all()],
            'reference': ref.reference if ref.reference else '',
            'description': ref.description if ref.description else '',
            'address': ref.address if ref.address else '',
            'lga': ref.lga.name if ref.lga else '',
            'dop_triggers': [i.name for i in ref.dop_triggers.all()],
            'url': ref.get_absolute_url(),
        }
        if ref.point:
            ref_document['point'] = [ref.point.x, ref.point.y]
        client.collections['referrals'].documents.upsert(ref_document)


def typesense_index_records(client, qs=None):
    """Index the passed-in queryset of records, or all of them.
    """
    if not qs:
        qs = Record.objects.current()
    for rec in qs:
        rec_document = {
            'record_id': rec.pk,
            'referral_id': rec.referral.pk,
            'name': rec.name,
            'description': rec.description if rec.description else '',
            'file_name': rec.filename,
            'file_type': rec.extension,
            'url': rec.get_absolute_url(),
        }
        # PDF document content.
        if rec.extension == 'PDF':
            content = pdfminer.high_level.extract_text(open(rec.uploaded_file.path, 'rb'))
            rec_document['file_content'] = content.replace('\n', ' ').strip()

        # MSG document content.
        if rec.extension == 'MSG':
            print(f'Indexing content for {rec}')
            message = Message(rec.uploaded_file.path)
            content = '{} {}'.format(message.subject, message.body.replace('\r\n', ' '))
            rec_document['file_content'] = content.strip()

        # DOCX document content.
        if rec.extension == 'DOCX':
            print(f'Indexing content for {rec}')
            content = docx2txt.process(rec.uploaded_file.path)
            rec_document['file_content'] = content.replace('\n', ' ').strip()

        client.collections['records'].documents.upsert(rec_document)
