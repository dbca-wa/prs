from datetime import date, datetime
from django.conf import settings
from django.urls import reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import TemplateView
from taggit.models import Tag
import xlsxwriter

from referral.models import Referral, Clearance, Task, TaskType
from referral.utils import breadcrumbs_li, is_model_or_string, prs_user


class ReportView(TemplateView):
    """Template view to allow filtering and download of data.
    """
    template_name = 'reports/reports.html'

    def get_context_data(self, **kwargs):
        context = super(ReportView, self).get_context_data(**kwargs)
        context['page_title'] = ' | '.join([settings.APPLICATION_ACRONYM, 'Reports'])
        links = [(reverse('site_home'), 'Home'), (None, 'Reports')]
        context['breadcrumb_trail'] = breadcrumbs_li(links)
        context['no_sidebar'] = True
        context['is_prs_user'] = prs_user(self.request)
        return context


class DownloadView(TemplateView):
    """A basic view to return a spreadsheet of PRS objects.
    """
    def dispatch(self, request, *args, **kwargs):
        # kwargs must include a Model class, or a string.
        # Determine the required model type.
        if 'model' in kwargs:
            self.model = is_model_or_string(kwargs.pop('model'))
        return super(DownloadView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        # Get any query parameters to filter the data.
        query_params = dict(request.GET.items())
        # Get the required model type from the query params.
        model = is_model_or_string(query_params.pop('model'))
        # Special case: region -> regions.
        region = query_params.pop('region__id', None)
        if region:
            if model._meta.model_name == 'referral':
                query_params['regions__id__in'] = [region]
            elif model._meta.model_name == 'task':
                query_params['referral__regions__id__in'] = [region]
            elif model._meta.model_name == 'clearance':
                query_params['condition__referral__regions__id__in'] = [region]
        # Special case: for clearances, follow dates through to linked task.
        if model._meta.model_name == 'clearance':
            state = query_params.pop('state__id', None)
            if state:
                query_params['task__state__pk'] = state
            referring_org = query_params.pop('referring_org__id', None)
            if referring_org:
                query_params['task__referral__referring_org__pk'] = referring_org
            start = query_params.pop('start_date__gte', None)
            if start:
                query_params['task__start_date__gte'] = start
            end = query_params.pop('start_date__lte', None)
            if end:
                query_params['task__start_date__lte'] = end
        # Special case: remove tag PKs from the query params.
        tag = query_params.pop('tag__id', None)
        if tag:
            tags = Tag.objects.filter(pk=tag)
        else:
            tags = None

        # Generate a HTTPResponse object to write to.
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        # Generate a blank Excel workbook.
        workbook = xlsxwriter.Workbook(
            response,
            options={
                'in_memory': True,
                'default_date_format': 'dd-mmm-yyyy',
                'remove_timezone': True,
            },
        )

        if model == Referral:
            response['Content-Disposition'] = f'attachment; filename=prs_referrals_{date.today().isoformat()}_{datetime.now().strftime("%H%M")}.xlsx'
            # Filter referral objects according to the parameters.
            referrals = Referral.objects.current().select_related(
                'type',
                'referring_org',
                'lga',
            ).filter(**query_params)
            if tags:  # Optional: filter by tags.
                referrals = referrals.filter(tags__in=tags).distinct()

            # Short circuit: disallow a report containing >10000 objects.
            if referrals.count() > 10000:
                return HttpResponseBadRequest('Report too large, apply additional filters')

            # Add a worksheet.
            ws = workbook.add_worksheet('Referrals')
            # Write the column headers to the new worksheet.
            row = 0
            ws.write_row(
                row=row,
                col=0,
                data=[
                    'Referral ID',
                    'Region(s)',
                    'Referrer',
                    'Type',
                    'Reference',
                    'Received',
                    'Description',
                    'Address',
                    'Triggers',
                    'Tags',
                    'File no.',
                    'LGA',
                ],
            )
            row += 1
            # Write the referral values to the worksheet.
            for r in referrals:
                ws.write_row(
                    row=row,
                    col=0,
                    data=[
                        r.pk,
                        r.regions_str,
                        r.referring_org.name,
                        r.type.name,
                        r.reference,
                        r.referral_date,
                        r.description,
                        r.address,
                        ', '.join([t.name for t in r.dop_triggers.all()]),
                        ', '.join([t.name for t in r.tags.all()]),
                        r.file_no,
                        r.lga.name if r.lga else '',
                    ],
                )
                row += 1

            # Set column widths.
            ws.set_column('A:A', width=10)
            ws.set_column('B:B', width=12)
            ws.set_column('C:C', width=38)
            ws.set_column('D:D', width=22)
            ws.set_column('E:F', width=12)
            ws.set_column('G:I', width=45)
            ws.set_column('J:J', width=15)
            ws.set_column('K:K', width=12)
            ws.set_column('L:L', width=30)

        elif model == Clearance:
            response['Content-Disposition'] = f'attachment; filename=prs_clearance_requests_{date.today().isoformat()}_{datetime.now().strftime("%H%M")}.xlsx'
            # Filter clearance objects according to the parameters.
            clearances = Clearance.objects.current().select_related(
                'condition',
                'task',
            ).filter(**query_params)

            # Short circuit: disallow a report containing >10000 objects.
            if clearances.count() > 10000:
                return HttpResponseBadRequest('Report too large, apply additional filters')

            # Add a worksheet.
            ws = workbook.add_worksheet('Clearances')
            # Write the column headers to the new worksheet.
            row = 0
            ws.write_row(
                row=row,
                col=0,
                data=[
                    'Referral ID',
                    'Region(s)',
                    'Reference',
                    'Condition no.',
                    'Approved condition',
                    'Category',
                    'Task description',
                    'Deposited plan no.',
                    'Assigned user',
                    'Status',
                    'Start date',
                    'Due date',
                    'Complete date',
                    'Stop date',
                    'Restart date',
                    'Total stop days',
                ],
            )
            row += 1

            # Write the clearance values to the worksheet.
            for c in clearances:
                ws.write_row(
                    row=row,
                    col=0,
                    data=[
                        c.condition.referral.pk,
                        c.condition.referral.regions_str,
                        c.condition.referral.reference,
                        c.condition.identifier,
                        c.condition.condition,
                        c.condition.category.name if c.condition.category else '',
                        c.task.description,
                        c.deposited_plan,
                        c.task.assigned_user.get_full_name(),
                        c.task.state.name,
                        c.task.start_date,
                        c.task.due_date,
                        c.task.complete_date,
                        c.task.stop_date,
                        c.task.restart_date,
                        c.task.stop_time,
                    ],
                )
                row += 1

            # Set column widths.
            ws.set_column('A:A', 9)
            ws.set_column('B:D', 12)
            ws.set_column('E:E', 45)
            ws.set_column('G:G', 45)
            ws.set_column('H:J', 18)
            ws.set_column('K:P', 10)

        elif model == Task:
            response['Content-Disposition'] = f'attachment; filename=prs_tasks_{date.today().isoformat()}_{datetime.now().strftime("%H%M")}.xlsx'

            # Filter task objects according to the parameters.
            tasks = Task.objects.current().select_related(
                'type',
                'referral',
                'assigned_user',
                'state',
            ).filter(**query_params)
            # Business rule: filter out 'Condition clearance' task types.
            cr = TaskType.objects.get(name='Conditions clearance request')
            tasks = tasks.exclude(type=cr)

            # Short circuit: disallow a report containing >10000 objects.
            if tasks.count() > 10000:
                return HttpResponseBadRequest('Report too large, apply additional filters')

            # Add a worksheet.
            ws = workbook.add_worksheet('Tasks')
            # Write the column headers to the new worksheet.
            row = 0
            ws.write_row(
                row=row,
                col=0,
                data=[
                    'Task ID',
                    'Region(s)',
                    'Referral ID',
                    'Referred by',
                    'Referral type',
                    'Reference',
                    'Referral received',
                    'Task type',
                    'Task status',
                    'Assigned user',
                    'Task start',
                    'Task due',
                    'Task complete',
                    'Stop date',
                    'Restart date',
                    'Total stop days',
                    'File no.',
                    'DoP triggers',
                    'Referral description',
                    'Referral address',
                    'LGA',
                ],
            )
            row += 1

            # Write the task values to the worksheet.
            for t in tasks:
                ws.write_row(
                    row=row,
                    col=0,
                    data=[
                        t.pk,
                        t.referral.regions_str,
                        t.referral.pk,
                        t.referral.referring_org.name,
                        t.referral.type.name,
                        t.referral.reference,
                        t.referral.referral_date,
                        t.type.name,
                        t.state.name,
                        t.assigned_user.get_full_name(),
                        t.start_date,
                        t.due_date,
                        t.complete_date,
                        t.stop_date,
                        t.restart_date,
                        t.stop_time,
                        t.referral.file_no,
                        ', '.join([i.name for i in t.referral.dop_triggers.all()]),
                        t.referral.description,
                        t.referral.address,
                        t.referral.lga.name if t.referral.lga else '',
                    ],
                )
                row += 1

            # Set column widths.
            ws.set_column('A:A', 9)
            ws.set_column('B:B', 12)
            ws.set_column('C:C', 9)
            ws.set_column('D:E', 35)
            ws.set_column('F:F', 20)
            ws.set_column('G:G', 14)
            ws.set_column('H:J', 20)
            ws.set_column('K:P', 11)
            ws.set_column('Q:Q', 25)
            ws.set_column('R:U', 45)

        workbook.close()
        return response
