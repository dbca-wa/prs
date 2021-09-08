from celery import shared_task
from indexer import utils


@shared_task
def index_object(pk, model, client=None):
    """Index a single PRS referral app object.
    """
    if not client:
        client = utils.typesense_client()

    if model == 'referral':
        from referral.models import Referral
        referral = Referral.objects.get(pk=pk)
        utils.typesense_index_referral(referral, client)
    elif model == 'record':
        from referral.models import Record
        record = Record.objects.get(pk=pk)
        utils.typesense_index_record(record, client)
    elif model == 'task':
        from referral.models import Task
        task = Task.objects.get(pk=pk)
        utils.typesense_index_task(task, client)
    elif model == 'note':
        from referral.models import Note
        note = Note.objects.get(pk=pk)
        utils.typesense_index_note(note, client)
    elif model == 'condition':
        from referral.models import Condition
        condition = Condition.objects.get(pk=pk)
        utils.typesense_index_condition(condition, client)
