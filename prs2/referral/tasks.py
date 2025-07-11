from celery import shared_task
from indexer import utils


@shared_task(default_retry_delay=10, max_retries=1)
def index_object(pk, model, client=None):
    """Index a single PRS referral app object."""
    if not client:
        client = utils.typesense_client()

    if model == "referral":
        from referral.models import Referral

        try:
            referral = Referral.objects.get(pk=pk)
            utils.typesense_index_referral(referral, client)
            return f"Updated referral {pk}"
        except Referral.DoesNotExist as exc:
            raise index_object.retry(exc=exc)
    elif model == "record":
        from referral.models import Record

        try:
            record = Record.objects.get(pk=pk)
            utils.typesense_index_record(record, client)
            return f"Updated record {pk}"
        except Record.DoesNotExist as exc:
            raise index_object.retry(exc=exc)
    elif model == "task":
        from referral.models import Task

        try:
            task = Task.objects.get(pk=pk)
            utils.typesense_index_task(task, client)
            return f"Updated task {pk}"
        except Task.DoesNotExist as exc:
            raise index_object.retry(exc=exc)
    elif model == "note":
        from referral.models import Note

        try:
            note = Note.objects.get(pk=pk)
            utils.typesense_index_note(note, client)
            return f"Updated note {pk}"
        except Note.DoesNotExist as exc:
            raise index_object.retry(exc=exc)
    elif model == "condition":
        from referral.models import Condition

        try:
            condition = Condition.objects.get(pk=pk)
            utils.typesense_index_condition(condition, client)
            return f"Updated condition {pk}"
        except Condition.DoesNotExist as exc:
            raise index_object.retry(exc=exc)
    else:
        return
