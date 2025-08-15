'use strict';

// NOTE: some global constants are set in the base template (context object).
const geoserver_wms_url = `${context.geoserver_url}/ows`;
const geoserver_wmts_url = `${context.geoserver_url}/gwc/service/wmts?service=WMTS&request=GetTile&version=1.0.0&format=image/png&tilematrixset=mercator&tilematrix=mercator:{z}&tilecol={x}&tilerow={y}`;

// Base layers
const virtualMosaic = L.tileLayer(`${geoserver_wmts_url}&layer=kaartdijin-boodja-private:virtual_mosaic`);
const mapboxStreets = L.tileLayer(`${geoserver_wmts_url}&layer=kaartdijin-boodja-public:mapbox-streets-public`);
const waCoast = L.tileLayer(`${geoserver_wmts_url}&layer=kaartdijin-boodja-private:WA_COAST_SMOOTHED`);

// Overlay layers
const cadastre = L.tileLayer(`${geoserver_wmts_url}&layer=kaartdijin-boodja-private:CPT_CADASTRE_SCDB`, {
  transparent: true,
  opacity: 0.75,
  minZoom: 13, // Limit the zoom at which this layer can be visible.
});
// Do not use WMTS for the PRS locations layer (live layer, avoid caching).
const prsLocations = L.tileLayer.wms(geoserver_wms_url, {
  layers: context.prs_layer_name,
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
});
const dbcaRegions = L.tileLayer(`${geoserver_wmts_url}&layer=kaartdijin-boodja-public:CPT_DBCA_REGIONS`, {
  transparent: true,
  opacity: 0.75,
});
const dbcaTenure = L.tileLayer(`${geoserver_wmts_url}&layer=kaartdijin-boodja-public:CPT_DBCA_LEGISLATED_TENURE`, {
  transparent: true,
  opacity: 0.75,
});
const regionalParks = L.tileLayer(`${geoserver_wmts_url}&layer=kaartdijin-boodja-private:CPT_REGIONAL_PARKS`, {
  transparent: true,
  opacity: 0.75,
});
const swanCannDevContArea = L.tileLayer(`${geoserver_wmts_url}&layer=kaartdijin-boodja-private:CPT_SWAN_CANN_DEV_CONT_AREA`, {
  transparent: true,
  opacity: 0.75,
});
const ucl = L.tileLayer(`${geoserver_wmts_url}&layer=kaartdijin-boodja-private:CPT_CADASTRE_UCL_1PL`, {
  transparent: true,
  opacity: 0.75,
});
const lgaBoundaries = L.tileLayer(`${geoserver_wmts_url}&layer=kaartdijin-boodja-public:CPT_LOCAL_GOVT_AREAS`, {
  transparent: true,
  opacity: 0.75,
});
const miningTenements = L.tileLayer(`${geoserver_wmts_url}&layer=kaartdijin-boodja-public:Mining_Tenements_DMIRS_003`, {
  transparent: true,
  opacity: 0.75,
});

// Define map.
const map = L.map('map', {
  center: [-31.96, 115.87],
  zoom: 16,
  minZoom: 6,
  maxZoom: 18,
  layers: [virtualMosaic, cadastre], // Sets default selections.
  attributionControl: false,
});

// Define layer groups.
const baseMaps = {
  'Virtual mosaic': virtualMosaic,
  'Mapbox streets': mapboxStreets,
  'WA coast': waCoast,
};
const overlayMaps = {
  Cadastre: cadastre,
  'PRS locations': prsLocations,
  'DBCA regions': dbcaRegions,
  'DBCA tenure': dbcaTenure,
  'Regional Parks': regionalParks,
  'Swan Canning Dev Ctrl Area': swanCannDevContArea,
  'Unallocated Crown Land': ucl,
  'LGA boundaries': lgaBoundaries,
  'Mining tenements': miningTenements,
};

// Define layer control.
L.control.layers(baseMaps, overlayMaps).addTo(map);

// Define scale bar
L.control.scale({ maxWidth: 500, imperial: false }).addTo(map);

function searchGeocoder(text, response) {
  // Use jQuery to query the Geocoder service API.
  return $.ajax({
    url: context.geocoder_url,
    data: { q: text },
    dataType: 'json',
    success: function (data) {
      response(data);
    },
  });
}

function filterGeocoderRecords(text, records) {
  // The stock leaflet-search function seemed to filter out all records from the response, so we override it.
  return records;
}

// Define geocoder search input.
map.addControl(
  new L.Control.Search({
    sourceData: searchGeocoder,
    filterData: filterGeocoderRecords,
    propertyName: 'address',
    propertyLoc: ['lat', 'lon'],
    // Other variables.
    delayType: 1000,
    textErr: '',
    zoom: 17,
    circleLocation: true,
    autoCollapse: true,
  })
);

// Define a custom lot filtering form Control
L.Control.LotFilter = L.Control.extend({
  options: {
    position: 'topleft',
    placeholder: 'Highlight Lots in view',
  },
  initialize: function (options) {
    L.Util.setOptions(this, options);
  },
  onAdd: function (map) {
    this._map = map;
    this._container = L.DomUtil.create('div', 'lotsearch-container');
    this._input = this._createInput(this.options.placeholder, 'form-control input-sm');
    return this._container;
  },
  _createInput: function (text, className) {
    const input = L.DomUtil.create('input', className, this._container);
    input.type = 'text';
    input.value = '';
    input.placeholder = text;
    input.role = 'search';
    input.id = 'id_input_lotSearch';
    // Prevent click progration (handled differently in IE11)
    if (!window.ActiveXObject && 'ActiveXObject' in window) {
      input.MSPointerDown = input.onmousedown = input.ondblclick = input.onpointerdown = L.DomEvent.stopPropagation;
    } else {
      L.DomEvent.disableClickPropagation(input); // Prevents input selection in IE11.
    }

    return input;
  },
  submit: function (e) {
    L.DomEvent.preventDefault(e);
  },
});
L.control.lotfilter = function (id, options) {
  return new L.Control.LotFilter(id, options);
};
// Add the custom control to the map, then set a change() event listener on it
const lotFilter = new L.Control.LotFilter({});
map.addControl(lotFilter);
$('input#id_input_lotSearch').change(function () {
  const lotname = $(this).val().toUpperCase();
  if (lotname) {
    findLot(lotname);
  }
});

// Add a feature group to the map to contain filtered Lot boundaries.
const lotsearchresults = new L.featureGroup();
map.addLayer(lotsearchresults);

const findLot = function (lotname) {
  // Generate our CQL filter.
  const filter = `CAD_LOT_NUMBER like '%${lotname}%' AND BBOX(SHAPE,${map.getBounds().toBBoxString()},'EPSG:4326')`;
  $.ajax({
    url: context.cadastre_query_url,
    data: { cql_filter: filter },
    dataType: 'json',
    success: function (data) {
      if (
        data.totalFeatures === 0 &&
        map.getMinZoom() < map.getZoom() &&
        confirm(`Couldn't find Survey Lot containing '${lotname}' in viewport, zoom out and try again?`)
      ) {
        map.zoomOut();
        findLot(lotname);
      }
      if (data.totalFeatures > 0) {
        lotsearchresults.clearLayers();
        lotsearchresults.addLayer(
          L.geoJson(data, {
            color: '#fa00ff',
            clickable: false,
          })
        );
        map.fitBounds(lotsearchresults.getBounds());
      }
    },
  });
};
// Log zoom level to console.
//map.on('zoomend', function (e) {console.log(e.target._zoom)});

// Add a fullscreen control to the map.
const fullScreen = new L.control.fullscreen();
map.addControl(fullScreen);

// Click event for the map.
map.on('click', function (evt) {
  const [x, y] = [evt.latlng.lng, evt.latlng.lat];
  const queryUrl = `${context.referral_point_search_url}?x=${x}&y=${y}`;
  // Query the proxied URL for any feature intersecting the clicked-on location.
  fetch(queryUrl)
    .then((resp) => resp.json())
    .then(function (data) {
      if (data.length > 0) {
        // data will be an array of referrals.
        let tableRows = '';
        data.forEach(function (el, idx, arr) {
          tableRows += `<tr><td><a href="${el.url}">${el.id}</a></td><td>${el.referral_date}</td><td>${el.type}</td><td>${el.reference}</td></tr>`;
        });

        // Generate popup HTML content
        let content = `<table class="table table-bordered table-striped table-sm">
  <thead>
    <tr><th>Referral ID</th><th>Date</th><th>Type</th><th>Reference</th></tr>
  </thead>
  <tbody>
    ${tableRows}
  </tbody>
</table>`;
        // Open the popup on the map.
        L.popup().setLatLng(evt.latlng).setContent(content).openOn(map);
      }
    });
});
