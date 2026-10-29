'use strict';
// Parse additional variables from the DOM element
const refListUrl = `${context.prs_object_list_url}`;
const reportDownloadUrl = `${context.reports_download_url}`;
const referralApiResourceUrl = `${context.referral_api_resource_url}`;
const clearanceApiResourceUrl = `${context.clearance_api_resource_url}`;
const taskApiResourceUrl = `${context.task_api_resource_url}`;
const regionApiResourceUrl = `${context.region_api_resource_url}`;
const referralTypeApiResourceUrl = `${context.referraltype_api_resource_url}`;
const organisationApiResourceUrl = `${context.organisation_api_resource_url}`;
const taskStateApiResourceUrl = `${context.taskstate_api_resource_url}`;
const taskTypeApiResourceUrl = `${context.tasktype_api_resource_url}`;
const userApiResourceUrl = `${context.user_api_resource_url}`;
const tagApiResourceUrl = `${context.tag_api_resource_url}`;
const spinner = new Spinner({ scale: 3, top: '120px' });

// DataTables inserts cell values into the DOM as HTML by default. API fields
// such as referral/task descriptions are user-supplied, so they must be
// escaped before being passed to DataTables to avoid stored XSS.
function escapeHtml(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderText(data) {
  return escapeHtml(data);
}

function renderReferralLink(data) {
  const id = encodeURIComponent(data).replace(/'/g, '%27');
  return `<a href='${refListUrl}${id}/'>${escapeHtml(data)}</a>`;
}

function startSpinner() {
  spinner.spin();
  $('#modal-spinner').append(spinner.el);
}

function _getSelectlistOptions(url, filters, dom_elements) {
  // Utility function to replace options in a select element(s)
  // by querying a passed-in endpoint URL.
  $.ajax({
    url: url,
    data: filters,
    success: function (data) {
      dom_elements.each(function () {
        this.disabled = true;
        this.options.length = 0;
        this.options.add(new Option('--------', ''));
        for (var i in data) {
          this.options.add(new Option(data[i].text, data[i].id));
        }
        this.disabled = false;
      });
    },
  });
}

function queryReferralFilters() {
  // Filters for the referral API query.
  var data = {};
  var region = $('select#filter-region-referral').val();
  if (region) {
    $.extend(data, { region__id: region });
  }
  var organisation = $('select#filter-organisation-referral').val();
  if (organisation) {
    $.extend(data, { referring_org__id: organisation });
  }
  var referralType = $('select#filter-referralType').val();
  if (referralType) {
    $.extend(data, { type__id: referralType });
  }
  var fromDate = $('input#filter-fromDate-referral').val();
  if (fromDate) {
    $.extend(data, { referral_date__gte: moment(fromDate, 'D/M/YYYY').format('YYYY-MM-DD') });
  }
  var toDate = $('input#filter-toDate-referral').val();
  if (toDate) {
    $.extend(data, { referral_date__lte: moment(toDate, 'D/M/YYYY').format('YYYY-MM-DD') });
  }
  var tags = $('#filter-referralTag').val();
  if (tags) {
    $.extend(data, { tag__id: tags });
  }
  return data;
}

function queryClearanceFilters() {
  // Filters for the clearance API query.
  var data = {};
  var region = $('select#filter-region-clearance').val();
  if (region) {
    $.extend(data, { region__id: region });
  }
  var organisation = $('select#filter-organisation-clearance').val();
  if (organisation) {
    $.extend(data, { referring_org__id: organisation });
  }
  var taskState = $('select#filter-taskState-clearance').val();
  if (taskState) {
    $.extend(data, { state__id: taskState });
  }
  var fromDate = $('input#filter-fromDate-clearance').val();
  if (fromDate) {
    $.extend(data, { start_date__gte: moment(fromDate, 'D/M/YYYY').format('YYYY-MM-DD') });
  }
  var toDate = $('input#filter-toDate-clearance').val();
  if (toDate) {
    $.extend(data, { start_date__lte: moment(toDate, 'D/M/YYYY').format('YYYY-MM-DD') });
  }
  return data;
}

function queryTaskFilters() {
  // Filters for the task API query.
  var data = {};
  var region = $('select#filter-region-task').val();
  if (region) {
    $.extend(data, { region__id: region });
  }
  var type = $('select#filter-taskType').val();
  if (type) {
    $.extend(data, { type__id: type });
  }
  var taskState = $('select#filter-taskState-task').val();
  if (taskState) {
    $.extend(data, { state__id: taskState });
  }
  var fromDate = $('input#filter-fromDate-task').val();
  if (fromDate) {
    $.extend(data, { start_date__gte: moment(fromDate, 'D/M/YYYY').format('YYYY-MM-DD') });
  }
  var toDate = $('input#filter-toDate-task').val();
  if (toDate) {
    $.extend(data, { start_date__lte: moment(toDate, 'D/M/YYYY').format('YYYY-MM-DD') });
  }
  var assigned = $('select#filter-assignedUser').val();
  if (assigned) {
    $.extend(data, { assigned_user__id: assigned });
  }
  return data;
}

function downloadData(model) {
  if (model == 'referral') {
    params = queryReferralFilters();
    params['model'] = model;
  } else if (model == 'clearance') {
    params = queryClearanceFilters();
    params['model'] = model;
  } else if (model == 'task') {
    params = queryTaskFilters();
    params['model'] = model;
  }
  window.open(`${reportDownloadUrl}?${$.param(params)}`, '_blank');
}

// DataTables configuration.
const configRefTable = {
  autoWidth: false,
  processing: true,
  serverSide: true, // NOTE: DataTables can't do client-side sorting for just the returned data :|
  searching: false, // Disable search filter.
  ordering: false, // Disable column sorting.
  pageLength: 25, // Initial number of results to show.
  responsive: true,
  pagingType: 'numbers',
  ajax: function (data, callback, settings) {
    delete data.columns; // Remove the columns array attribute to shorten the query params.
    delete data.search;
    data.limit = settings._iDisplayLength;
    data.offset = settings._iDisplayStart;
    var params = $.extend({}, data, queryReferralFilters());
    $.get(
      referralApiResourceUrl,
      params, // Query parameters for the API call.
      function (resp) {
        spinner.stop();
        // Map the API response to the DataTables format and pass it to DataTables callback.
        callback({
          data: JSON.parse(JSON.stringify(resp.objects)),
          recordsTotal: JSON.parse(JSON.stringify(resp.count)),
          recordsFiltered: JSON.parse(JSON.stringify(resp.count)),
        });
      }
    );
  },
  columns: [
    {
      data: 'id',
      render: function (data, type, row, meta) {
        return renderReferralLink(data);
      },
    },
    { data: 'regions', render: renderText },
    { data: 'referring_org', render: renderText },
    { data: 'type', render: renderText },
    { data: 'reference', render: renderText },
    {
      data: 'referral_date',
      type: 'date',
      render: function (data, type, row, meta) {
        var d = new Date(data);
        return escapeHtml(d.toDateString());
      },
    },
    {
      data: 'tags',
      render: function (data, type, row, meta) {
        return data.map(escapeHtml).join(', ');
      },
    },
    { data: 'description', render: renderText },
  ],
};

const configClearTable = {
  autoWidth: false,
  processing: true,
  serverSide: true,
  searching: false, // Disable search filter.
  ordering: false, // Disable column sorting.
  pageLength: 25, // Initial number of results to show.
  responsive: true,
  pagingType: 'numbers',
  ajax: function (data, callback, settings) {
    delete data.columns; // Remove the columns array attribute to shorten the query params.
    delete data.search;
    data.limit = settings._iDisplayLength;
    data.offset = settings._iDisplayStart;
    var params = $.extend({}, data, queryClearanceFilters());
    $.get(
      clearanceApiResourceUrl,
      params, // Query parameters for the API call.
      function (resp) {
        spinner.stop();
        // Map the API response to the DataTables format and pass it to DataTables callback.
        callback({
          data: JSON.parse(JSON.stringify(resp.objects)),
          recordsTotal: JSON.parse(JSON.stringify(resp.count)),
          recordsFiltered: JSON.parse(JSON.stringify(resp.count)),
        });
      }
    );
  },
  columns: [
    {
      data: 'referral_id',
      render: function (data, type, row, meta) {
        return renderReferralLink(data);
      },
    },
    { data: 'regions', render: renderText },
    { data: 'identifier', render: renderText },
    {
      data: 'condition',
      render: function (data, type, row, meta) {
        return `<div>${escapeHtml(data)}</div>`;
      },
    },
    { data: 'category', render: renderText },
    { data: 'description', render: renderText },
    { data: 'deposited_plan', render: renderText },
    { data: 'assigned_user', render: renderText },
    { data: 'state', render: renderText },
  ],
};

const configTaskTable = {
  autoWidth: false,
  processing: true,
  serverSide: true,
  searching: false, // Disable search filter.
  ordering: false, // Disable column sorting.
  pageLength: 25, // Initial number of results to show.
  responsive: true,
  pagingType: 'numbers',
  ajax: function (data, callback, settings) {
    delete data.columns; // Remove the columns array attribute to shorten the query params.
    delete data.search;
    data.limit = settings._iDisplayLength;
    data.offset = settings._iDisplayStart;
    var params = $.extend({}, data, queryTaskFilters());
    $.get(
      taskApiResourceUrl,
      params, // Query parameters for the API call.
      function (resp) {
        spinner.stop();
        // Map the API response to the DataTables format and pass it to DataTables callback.
        callback({
          data: JSON.parse(JSON.stringify(resp.objects)),
          recordsTotal: JSON.parse(JSON.stringify(resp.count)),
          recordsFiltered: JSON.parse(JSON.stringify(resp.count)),
        });
      }
    );
  },
  columns: [
    {
      data: 'referral_id',
      render: function (data, type, row, meta) {
        return renderReferralLink(data);
      },
    },
    { data: 'referral_reference', render: renderText },
    { data: 'regions', render: renderText },
    { data: 'assigned_user', render: renderText },
    { data: 'type', render: renderText },
    { data: 'description', render: renderText },
    { data: 'state', render: renderText },
    {
      data: 'start_date',
      type: 'date',
      render: function (data, type, row, meta) {
        return escapeHtml(new Date(data).toDateString());
      },
    },
    {
      data: 'due_date',
      type: 'date',
      render: function (data, type, row, meta) {
        return escapeHtml(new Date(data).toDateString());
      },
    },
    {
      data: 'complete_date',
      type: 'date',
      render: function (data, type, row, meta) {
        if (data) {
          return escapeHtml(new Date(data).toDateString());
        } else {
          return '';
        }
      },
    },
  ],
};

// Document ready
$(function () {
  startSpinner();

  // Initialise the DataTables.
  var refDataTable = $('table#referralsTable').DataTable(configRefTable);
  var clearDataTable = $('table#clearancesTable').DataTable(configClearTable);
  var taskDataTable = $('table#tasksTable').DataTable(configTaskTable);

  // Initialise datepicker widgets
  $('.dateinput')
    .datepicker({
      format: 'd/m/yyyy',
      autoclose: true,
      todayHighlight: true,
    })
    .on('changeDate', function (e) {
      // Onchange event for all datepickers (separate to below, because
      // the widget triggers multiple change events.
      if (e.target.id.indexOf('referral') > -1) {
        startSpinner();
        refDataTable.ajax.reload();
      } else if (e.target.id.indexOf('clearance') > -1) {
        startSpinner();
        clearDataTable.ajax.reload();
      } else if (e.target.id.indexOf('task') > -1) {
        startSpinner();
        taskDataTable.ajax.reload();
      }
    });

  // Initialise filter select lists.
  const selectFilters = { selectlist: '' };
  _getSelectlistOptions(regionApiResourceUrl, selectFilters, $('[id^=filter-region]'));
  _getSelectlistOptions(referralTypeApiResourceUrl, selectFilters, $('[id^=filter-referralType]'));
  _getSelectlistOptions(organisationApiResourceUrl, selectFilters, $('[id^=filter-organisation]'));
  _getSelectlistOptions(taskStateApiResourceUrl, selectFilters, $('[id^=filter-taskState]'));
  _getSelectlistOptions(taskTypeApiResourceUrl, selectFilters, $('[id^=filter-taskType]'));
  _getSelectlistOptions(userApiResourceUrl, selectFilters, $('[id^=filter-assignedUser]'));
  _getSelectlistOptions(tagApiResourceUrl, selectFilters, $('[id^=filter-referralTag]'));

  // Onchange events for Referral filters.
  $('#filter-region-referral, #filter-organisation-referral, #filter-referralType, #filter-referralTag').change(function () {
    startSpinner();
    refDataTable.ajax.reload();
  });

  // Onchange events for Clearance filters.
  $('#filter-region-clearance, #filter-organisation-clearance, #filter-taskState-clearance').change(function () {
    startSpinner();
    clearDataTable.ajax.reload();
  });
  // Onchange events for Task filters.
  $('#filter-taskType, #filter-region-task, #filter-taskState-task, #filter-assignedUser').change(function () {
    startSpinner();
    taskDataTable.ajax.reload();
  });

  // Click events for the 'Download' buttons.
  $('a#id_download_referrals').click(function () {
    downloadData('referral');
  });
  $('a#id_download_clearances').click(function () {
    downloadData('clearance');
  });
  $('a#id_download_tasks').click(function () {
    downloadData('task');
  });
});
