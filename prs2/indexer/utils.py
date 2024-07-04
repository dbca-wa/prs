from django.conf import settings
import docx2txt
from extract_msg import Message
from io import BytesIO
from pdfminer import high_level
import re
import typesense
from unidecode import unidecode


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
        'connection_timeout_seconds': settings.TYPESENSE_CONN_TIMEOUT,
    })
    return client


def typesense_index_referral(ref, client=None):
    """Index a single referral in Typesense.
    """
    if not client:
        client = typesense_client()

    ref_document = {
        'id': str(ref.pk),
        'created': ref.created.timestamp(),
        'type': ref.type.name,
        'referring_org': ref.referring_org.name,
        'regions': [i.name for i in ref.regions.all()],
        'reference': ref.reference if ref.reference else '',
        'description': ref.description if ref.description else '',
        'address': ref.address if ref.address else '',
        'lga': ref.lga.name if ref.lga else '',
        'dop_triggers': [i.name for i in ref.dop_triggers.all()],
    }
    if ref.point:
        ref_document['point'] = [ref.point.x, ref.point.y]
    client.collections['referrals'].documents.upsert(ref_document)


def typesense_index_record(rec, client=None):
    """Index a single record in Typesense.
    """
    if not client:
        client = typesense_client()

    rec_document = {
        'id': str(rec.pk),
        'created': rec.created.timestamp(),
        'referral_id': rec.referral.pk,
        'name': rec.name,
        'description': rec.description if rec.description else '',
        'file_name': rec.filename,
        'file_type': rec.extension,
    }
    file_content = ''

    # PDF document content.
    if rec.extension == 'PDF':
        try:
            # PDF text extraction can be a little error-prone.
            # In the event of an exception here, we'll just accept it and pass.
            if settings.LOCAL_MEDIA_STORAGE:
                file_content = high_level.extract_text(open(rec.uploaded_file.path, 'rb'))
            else:
                # Read the upload blob content into an in-memory file.
                tmp = BytesIO()
                tmp.write(rec.uploaded_file.read())
                file_content = high_level.extract_text(tmp)
        except:
            pass

    # MSG document content.
    if rec.extension == 'MSG':
        if settings.LOCAL_MEDIA_STORAGE:
            message = Message(rec.uploaded_file.path)
        else:
            # Read the upload blob content into an in-memory file.
            tmp = BytesIO()
            tmp.write(rec.uploaded_file.read())
            message = Message(tmp)
        file_content = f'{message.subject} {message.body}'

    # DOCX document content.
    if rec.extension == 'DOCX':
        if settings.LOCAL_MEDIA_STORAGE:
            file_content = docx2txt.process(rec.uploaded_file.path)
        else:
            # Read the upload blob content into an in-memory file.
            tmp = BytesIO()
            tmp.write(rec.uploaded_file.read())
            file_content = docx2txt.process(tmp)

    # TXT document content.
    if rec.extension == 'TXT':
        if settings.LOCAL_MEDIA_STORAGE:
            file_content = open(rec.uploaded_file.path, 'r').read()
        else:
            # Read the upload blob content directly.
            file_content = rec.uploaded_file.read()

    # Trim down the file content a little to aid indexing.
    if file_content:
        # Decode a bytes object to a string.
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        # Replace punctuation with a space.
        file_content = re.sub(r'[^\w\s]', ' ', file_content)
        # Replace newlines with a space.
        file_content = file_content.replace('\r', '').replace('\n', ' ')
        # Replace multiple spaces with a single one.
        file_content = re.sub(r'\s+', ' ', file_content)
        file_content = file_content.strip()
        # Transliterate some unicode characters to ASCII.
        file_content = unidecode(file_content)

    rec_document['file_content'] = file_content
    client.collections['records'].documents.upsert(rec_document)


def typesense_index_note(note, client=None):
    """Index a single note in Typesense.
    """
    if not client:
        client = typesense_client()

    note_document = {
        'id': str(note.pk),
        'created': note.created.timestamp(),
        'referral_id': note.referral.pk,
        'note': note.note,
    }
    client.collections['notes'].documents.upsert(note_document)


def typesense_index_task(task, client=None):
    """Index a single task in Typesense.
    """
    if not client:
        client = typesense_client()

    task_document = {
        'id': str(task.pk),
        'created': task.created.timestamp(),
        'referral_id': task.referral.pk,
        'description': task.description if task.description else '',
        'assigned_user': task.assigned_user.get_full_name(),
    }
    client.collections['tasks'].documents.upsert(task_document)


def typesense_index_condition(con, client=None):
    """Index a single condition in Typesense.
    """
    if not client:
        client = typesense_client()

    condition_document = {
        'id': str(con.pk),
        'created': con.created.timestamp(),
        'referral_id': con.referral.pk if con.referral else None,
        'proposed_condition': con.proposed_condition if con.proposed_condition else '',
        'approved_condition': con.condition if con.condition else '',
    }
    client.collections['conditions'].documents.upsert(condition_document)
