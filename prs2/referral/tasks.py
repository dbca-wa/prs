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
        try:
            referral = Referral.objects.get(pk=pk)
            utils.typesense_index_referral(referral, client)
        except Referral.DoesNotExist:
            return
    elif model == 'record':
        from referral.models import Record
        try:
            record = Record.objects.get(pk=pk)
            utils.typesense_index_record(record, client)
        except Record.DoesNotExist:
            return
    elif model == 'task':
        from referral.models import Task
        try:
            task = Task.objects.get(pk=pk)
            utils.typesense_index_task(task, client)
        except Task.DoesNotExist:
            return
    elif model == 'note':
        from referral.models import Note
        try:
            note = Note.objects.get(pk=pk)
            utils.typesense_index_note(note, client)
        except Note.DoesNotExist:
            return
    elif model == 'condition':
        from referral.models import Condition
        try:
            condition = Condition.objects.get(pk=pk)
            utils.typesense_index_condition(condition, client)
        except Condition.DoesNotExist:
            return

    return
