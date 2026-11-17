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
const spinner = new Spinner({ scale: 3, top: '120px', left: '50%' });
// The initial page load requests all three tables at once, so the spinner is
// reference-counted: it is only removed when every in-flight request is done.
let pendingRequests = 0;

// DataTables inserts cell values into the DOM as HTML by default. API fields
// such as referral/task descriptions are user-supplied, so they must be
// escaped before being passed to DataTables to avoid stored XSS.
function escapeHtml(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function renderText(data) {
  return escapeHtml(data);
}

function renderReferralLink(data) {
  if (data === null || data === undefined) {
    return '';
  }
  const id = encodeURIComponent(data).replace(/'/g, '%27');
  return `<a href='${refListUrl}${id}/'>${escapeHtml(data)}</a>`;
}

function renderDate(data) {
  // API dates are ISO (YYYY-MM-DD) or null. Parse at local midnight so the
  // displayed day doesn't shift for users outside UTC, and never render the
  // epoch ("Thu Jan 01 1970") for a missing date.
  if (!data) {
    return '';
  }
  const d = new Date(`${data}T00:00:00`);
  return isNaN(d.getTime()) ? '' : escapeHtml(d.toDateString());
}

function parseDateParam(value) {
  // Parse a d/m/yyyy value entered via the datepicker. Returns '' for an
  // incomplete or invalid date so the API never receives "Invalid date".
  const parsed = moment(value, 'D/M/YYYY', true);
  return parsed.isValid() ? parsed.format('YYYY-MM-DD') : '';
}

function startSpinner() {
  pendingRequests += 1;
  if (pendingRequests === 1) {
    spinner.spin();
    $('#modal-spinner').append(spinner.el);
  }
}

function stopSpinner() {
  pendingRequests = Math.max(0, pendingRequests - 1);
  if (pendingRequests === 0) {
    spinner.stop();
  }
}

function _getSelectlistOptions(url, filters, dom_elements) {
  // Utility function to replace options in a select element(s)
  // by querying a passed-in endpoint URL.
  dom_elements.prop('disabled', true);
  $.ajax({
    url: url,
    data: filters,
  })
    .done(function (data) {
      if (!Array.isArray(data)) {
        console.error(`Unexpected select list response from ${url}`);
        return;
      }
      dom_elements.each(function () {
        this.options.length = 0;
        this.options.add(new Option('--------', ''));
        data.forEach(function (item) {
          this.options.add(new Option(item.text, item.id));
        }, this);
      });
    })
    .fail(function (xhr) {
      console.error(`Could not load select list options from ${url} (${xhr.status})`);
    })
    .always(function () {
      // Re-enable the selects even when the request failed, otherwise the
      // filter stays permanently greyed out.
      dom_elements.prop('disabled', false);
    });
}

function loadTableRows(url, params, callback) {
  // Shared DataTables AJAX loader: fetch one page of results from an API
  // endpoint and map the {count, objects} response to DataTables' shape.
  startSpinner();
  $.get(url, params)
    .done(function (resp) {
      callback({
        data: resp.objects || [],
        recordsTotal: resp.count || 0,
        recordsFiltered: resp.count || 0,
      });
    })
    .fail(function (xhr) {
      // Fall back to an empty table; otherwise DataTables' callback is never
      // invoked and the table stays stuck on the "Processing" overlay.
      console.error(`Report data request failed (${xhr.status}): ${url}`);
      callback({ data: [], recordsTotal: 0, recordsFiltered: 0 });
    })
    .always(stopSpinner);
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
  var fromDate = parseDateParam($('input#filter-fromDate-referral').val());
  if (fromDate) {
    $.extend(data, { referral_date__gte: fromDate });
  }
  var toDate = parseDateParam($('input#filter-toDate-referral').val());
  if (toDate) {
    $.extend(data, { referral_date__lte: toDate });
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
  var fromDate = parseDateParam($('input#filter-fromDate-clearance').val());
  if (fromDate) {
    $.extend(data, { start_date__gte: fromDate });
  }
  var toDate = parseDateParam($('input#filter-toDate-clearance').val());
  if (toDate) {
    $.extend(data, { start_date__lte: toDate });
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
  var fromDate = parseDateParam($('input#filter-fromDate-task').val());
  if (fromDate) {
    $.extend(data, { start_date__gte: fromDate });
  }
  var toDate = parseDateParam($('input#filter-toDate-task').val());
  if (toDate) {
    $.extend(data, { start_date__lte: toDate });
  }
  var assigned = $('select#filter-assignedUser').val();
  if (assigned) {
    $.extend(data, { assigned_user__id: assigned });
  }
  return data;
}

function downloadData(model) {
  var params;
  if (model === 'referral') {
    params = queryReferralFilters();
  } else if (model === 'clearance') {
    params = queryClearanceFilters();
  } else if (model === 'task') {
    params = queryTaskFilters();
  } else {
    return; // Unknown model: nothing to download.
  }
  params['model'] = model;
  // Trigger the download via a synthetic link rather than window.location, so
  // an error response (e.g. "Report too large") opens in a new tab instead of
  // navigating away from the reports page.
  var link = document.createElement('a');
  link.href = `${reportDownloadUrl}?${$.param(params)}`;
  link.target = '_blank';
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
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
    loadTableRows(referralApiResourceUrl, params, callback); // Query parameters for the API call.
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
        return renderDate(data);
      },
    },
    {
      data: 'tags',
      render: function (data, type, row, meta) {
        return (data || []).map(escapeHtml).join(', ');
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
    loadTableRows(clearanceApiResourceUrl, params, callback); // Query parameters for the API call.
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
    loadTableRows(taskApiResourceUrl, params, callback); // Query parameters for the API call.
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
        return renderDate(data);
      },
    },
    {
      data: 'due_date',
      type: 'date',
      render: function (data, type, row, meta) {
        return renderDate(data);
      },
    },
    {
      data: 'complete_date',
      type: 'date',
      render: function (data, type, row, meta) {
        return renderDate(data);
      },
    },
  ],
};

// Document ready
$(function () {
  // Initialise the DataTables. The shared loader starts and stops the spinner,
  // so no explicit spinner calls are needed around reloads.
  var refDataTable = $('table#referralsTable').DataTable(configRefTable);
  var clearDataTable = $('table#clearancesTable').DataTable(configClearTable);
  var taskDataTable = $('table#tasksTable').DataTable(configTaskTable);

  // Tables in inactive tabs are initialised while hidden, so column widths are
  // calculated against a zero-width container. Recalculate when a tab becomes
  // visible. The CDN bundle does not include the Responsive extension, so the
  // `responsive: true` config option is inert and `table.responsive` is absent.
  $('a[data-bs-toggle="tab"]').on('shown.bs.tab', function (e) {
    var pane = $(e.target).attr('data-bs-target') || $(e.target).attr('href');
    $(pane)
      .find('table.dataTable')
      .each(function () {
        var table = $(this).DataTable();
        table.columns.adjust();
        if (table.responsive) {
          table.responsive.recalc();
        }
      });
  });

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
        refDataTable.ajax.reload();
      } else if (e.target.id.indexOf('clearance') > -1) {
        clearDataTable.ajax.reload();
      } else if (e.target.id.indexOf('task') > -1) {
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
    refDataTable.ajax.reload();
  });

  // Onchange events for Clearance filters.
  $('#filter-region-clearance, #filter-organisation-clearance, #filter-taskState-clearance').change(function () {
    clearDataTable.ajax.reload();
  });
  // Onchange events for Task filters.
  $('#filter-taskType, #filter-region-task, #filter-taskState-task, #filter-assignedUser').change(function () {
    taskDataTable.ajax.reload();
  });

  // Click events for the 'Download' buttons. The anchors use href="#", so
  // suppress the default navigation; the download itself is a navigation.
  $('a#id_download_referrals').click(function (e) {
    e.preventDefault();
    downloadData('referral');
  });
  $('a#id_download_clearances').click(function (e) {
    e.preventDefault();
    downloadData('clearance');
  });
  $('a#id_download_tasks').click(function (e) {
    e.preventDefault();
    downloadData('task');
  });
});
