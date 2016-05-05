from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.views.generic import TemplateView
from openpyxl import Workbook
from referral.models import Referral, Clearance, Task
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
    """A basic view to return a spreadsheet of referral objects.
    """
    def dispatch(self, request, *args, **kwargs):
        # kwargs must include a Model class, or a string.
        # Determine the required model type.
        if 'model' in kwargs:
            self.model = is_model_or_string(kwargs.pop('model'))
        return super(DownloadView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        # Get any query parameters to filter the data.
        query_params = dict(request.GET.iteritems())
        # Get the required model type from the query params.
        model = is_model_or_string(query_params.pop('model'))

        # Generate a blank Excel workbook.
        wb = Workbook()
        ws = wb.active  # The worksheet

        # Generate a HTTPResponse object to write to.
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        if model == Referral:
            response['Content-Disposition'] = 'attachment; filename=prs_referrals.xlsx'
            # Filter referral objects according to the parameters.
            referrals = Referral.objects.filter(**query_params)
            # Write the column headers to the new worksheet.
            headers = [
                'Referral ID', 'Region(s)', 'Referrer', 'Type', 'Reference',
                'Received', 'Description', 'Address', 'Triggers', 'Tags',
                'File no.']
            for col, value in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col)
                cell.value = value
            # Write the referral values to the worksheet.
            for row, r in enumerate(referrals, 2):  # Start at row 2
                cell = ws.cell(row=row, column=1)
                cell.value = r.pk
                cell = ws.cell(row=row, column=2)
                cell.value = r.regions_str
                cell = ws.cell(row=row, column=3)
                cell.value = r.referring_org.name
                cell = ws.cell(row=row, column=4)
                cell.value = r.type.name
                cell = ws.cell(row=row, column=5)
                cell.value = r.reference
                cell = ws.cell(row=row, column=6)
                cell.value = r.referral_date.strftime('%d/%b/%Y')
                cell = ws.cell(row=row, column=7)
                cell.value = r.description
                cell = ws.cell(row=row, column=8)
                cell.value = r.address
                cell = ws.cell(row=row, column=9)
                cell.value = ', '.join([t.name for t in r.dop_triggers.all()])
                cell = ws.cell(row=row, column=10)
                cell.value = ', '.join([t.name for t in r.tags.all()])
                cell = ws.cell(row=row, column=11)
                cell.value = r.file_no
        elif model == Clearance:
            response['Content-Disposition'] = 'attachment; filename=prs_clearance_requests.xlsx'
            # Filter clearance objects according to the parameters.
            clearances = Clearance.objects.filter(**query_params)
            # Write the column headers to the new worksheet.
            headers = [
                'Referral ID', 'Region(s)', 'Reference', 'Condition no.',
                'Approved condition', 'Category', 'Task description',
                'Deposited plan no.', 'Assigned user', 'Status', 'Start date',
                'Due date', 'Complete date']
            for col, value in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col)
                cell.value = value
            # Write the clearance values to the worksheet.
            for row, c in enumerate(clearances, 2):  # Start at row 2
                cell = ws.cell(row=row, column=1)
                cell.value = c.condition.referral.pk
                cell = ws.cell(row=row, column=2)
                cell.value = c.condition.referral.regions_str
                cell = ws.cell(row=row, column=3)
                cell.value = c.condition.referral.reference
                cell = ws.cell(row=row, column=4)
                cell.value = c.condition.identifier
                cell = ws.cell(row=row, column=5)
                cell.value = c.condition.condition
                cell = ws.cell(row=row, column=6)
                if c.condition.category:
                    cell.value = c.condition.category.name
                cell = ws.cell(row=row, column=7)
                cell.value = c.task.description
                cell = ws.cell(row=row, column=8)
                cell.value = c.deposited_plan
                cell = ws.cell(row=row, column=9)
                cell.value = c.task.assigned_user.get_full_name()
                cell = ws.cell(row=row, column=10)
                cell.value = c.task.state.name
                cell = ws.cell(row=row, column=11)
                if c.task.start_date:
                    cell.value = c.task.start_date.strftime('%d/%b/%Y')
                cell = ws.cell(row=row, column=12)
                if c.task.due_date:
                    cell.value = c.task.due_date.strftime('%d/%b/%Y')
                cell = ws.cell(row=row, column=13)
                if c.task.complete_date:
                    cell.value = c.task.complete_date.strftime('%d/%b/%Y')
        elif model == Task:
            response['Content-Disposition'] = 'attachment; filename=prs_tasks.xlsx'
            # Filter task objects according to the parameters.
            tasks = Task.objects.filter(**query_params)
            # Write the column headers to the new worksheet.
            headers = [
                'Task ID', 'Region(s)', 'Referral ID', 'Referred by',
                'Referral type', 'Reference', 'Referral received', 'Task type',
                'Task status', 'Assigned user', 'Task start', 'Task due',
                'Task complete', 'Stop date', 'Restart date', 'Total stop days',
                'File no.', 'DoP triggers', 'Referral description', 'Referral address']
            for col, value in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col)
                cell.value = value
            # Write the task values to the worksheet.
            for row, t in enumerate(tasks, 2):  # Start at row 2
                cell = ws.cell(row=row, column=1)
                cell.value = t.pk
                cell = ws.cell(row=row, column=2)
                cell.value = t.referral.regions_str
                cell = ws.cell(row=row, column=3)
                cell.value = t.referral.pk
                cell = ws.cell(row=row, column=4)
                cell.value = t.referral.referring_org.name
                cell = ws.cell(row=row, column=5)
                cell.value = t.referral.type.name
                cell = ws.cell(row=row, column=6)
                cell.value = t.referral.reference
                cell = ws.cell(row=row, column=7)
                cell.value = t.referral.referral_date.strftime('%d/%b/%Y')
                cell = ws.cell(row=row, column=8)
                cell.value = t.type.name
                cell = ws.cell(row=row, column=9)
                cell.value = t.state.name
                cell = ws.cell(row=row, column=10)
                cell.value = t.assigned_user.get_full_name()
                cell = ws.cell(row=row, column=11)
                if t.start_date:
                    cell.value = t.start_date.strftime('%d/%b/%Y')
                cell = ws.cell(row=row, column=12)
                if t.due_date:
                    cell.value = t.due_date.strftime('%d/%b/%Y')
                cell = ws.cell(row=row, column=13)
                if t.complete_date:
                    cell.value = t.complete_date.strftime('%d/%b/%Y')
                cell = ws.cell(row=row, column=14)
                if t.stop_date:
                    cell.value = t.stop_date.strftime('%d/%b/%Y')
                cell = ws.cell(row=row, column=15)
                if t.restart_date:
                    cell.value = t.restart_date.strftime('%d/%b/%Y')
                cell = ws.cell(row=row, column=16)
                cell.value = t.stop_time
                cell = ws.cell(row=row, column=17)
                cell.value = t.referral.file_no
                cell = ws.cell(row=row, column=18)
                cell.value = ', '.join([i.name for i in t.referral.dop_triggers.all()])
                cell = ws.cell(row=row, column=19)
                cell.value = t.referral.description
                cell = ws.cell(row=row, column=20)
                cell.value = t.referral.address

        wb.save(response)  # Save the workbook contents to the response.
        return response
