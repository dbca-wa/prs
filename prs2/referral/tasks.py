from celery import shared_task
from indexer.utils import (
    get_typesense_client,
    typesense_index_condition,
    typesense_index_note,
    typesense_index_record,
    typesense_index_referral,
    typesense_index_task,
)
from referral.utils import get_uploaded_file_content


@shared_task(default_retry_delay=10, max_retries=3)
def index_record(pk):
    from referral.models import Record

    try:
        record = Record.objects.get(pk=pk)
        if not record.uploaded_file_content:
            record.uploaded_file_content = get_uploaded_file_content(record)
            # Set index=False to prevent an infinite save loop.
            record.save(index=False)
            return f"Indexed record {pk} file content"
    except Record.DoesNotExist as exception:
        raise index_record.retry(exc=exception)


@shared_task(default_retry_delay=10, max_retries=1)
def index_object(pk, model, client=None):
    """Index a single PRS referral app object."""
    if not client:
        client = get_typesense_client()

    if model == "referral":
        from referral.models import Referral

        try:
            referral = Referral.objects.get(pk=pk)
            typesense_index_referral(referral, client)
            return f"Indexed referral {pk} in Typesense"
        except Referral.DoesNotExist as exc:
            raise index_object.retry(exc=exc)
    elif model == "record":
        from referral.models import Record

        try:
            record = Record.objects.get(pk=pk)
            typesense_index_record(record, client)
            return f"Indexed record {pk} in Typesense"
        except Record.DoesNotExist as exc:
            raise index_object.retry(exc=exc)
    elif model == "task":
        from referral.models import Task

        try:
            task = Task.objects.get(pk=pk)
            typesense_index_task(task, client)
            return f"Indexed task {pk} in Typesense"
        except Task.DoesNotExist as exc:
            raise index_object.retry(exc=exc)
    elif model == "note":
        from referral.models import Note

        try:
            note = Note.objects.get(pk=pk)
            typesense_index_note(note, client)
            return f"Indexed note {pk} in Typesense"
        except Note.DoesNotExist as exc:
            raise index_object.retry(exc=exc)
    elif model == "condition":
        from referral.models import Condition

        try:
            condition = Condition.objects.get(pk=pk)
            typesense_index_condition(condition, client)
            return f"Indexed condition {pk} in Typesense"
        except Condition.DoesNotExist as exc:
            raise index_object.retry(exc=exc)
    else:
        return
