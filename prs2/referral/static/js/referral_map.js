'use strict';

// NOTE: some global constants are set in the base template (context object).
const geoserver_wms_url = `${context.geoserver_url}/ows`;

// Base layers
const virtualMosaic = L.tileLayer.wms(geoserver_wms_url, {
  layers: 'kaartdijin-boodja-private:virtual_mosaic',
});
const mapboxStreets = L.tileLayer.wms(geoserver_wms_url, {
  layers: 'kaartdijin-boodja-public:mapbox-streets-public',
});
const waCoast = L.tileLayer.wms(geoserver_wms_url, {
  layers: 'kaartdijin-boodja-private:WA_COAST_SMOOTHED',
});

// Overlay layers
const cadastre = L.tileLayer.wms(geoserver_wms_url, {
  layers: 'kaartdijin-boodja-private:CPT_CADASTRE_SCDB',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
  minZoom: 13,
});
const prsLocations = L.tileLayer.wms(geoserver_wms_url, {
  layers: 'kaartdijin-boodja-private:prs_locations',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
});
const dbcaRegions = L.tileLayer.wms(geoserver_wms_url, {
  layers: 'kaartdijin-boodja-public:CPT_DBCA_REGIONS',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
});
const dbcaTenure = L.tileLayer.wms(geoserver_wms_url, {
  layers: 'kaartdijin-boodja-public:CPT_DBCA_LEGISLATED_TENURE',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
});
const regionalParks = L.tileLayer.wms(geoserver_wms_url, {
  layers: 'kaartdijin-boodja-private:CPT_REGIONAL_PARKS',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
});
const swanCannDevContArea = L.tileLayer.wms(geoserver_wms_url, {
  layers: 'kaartdijin-boodja-private:CPT_SWAN_CANN_DEV_CONT_AREA',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
});
const ucl = L.tileLayer.wms(geoserver_wms_url, {
  layers: 'kaartdijin-boodja-private:CPT_CADASTRE_UCL_1PL',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
});
const lgaBoundaries = L.tileLayer.wms(geoserver_wms_url, {
  layers: 'kaartdijin-boodja-public:CPT_LOCAL_GOVT_AREAS',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
});
const miningTenements = L.tileLayer.wms(geoserver_wms_url, {
  layers: '	kaartdijin-boodja-public:Mining_Tenements_DMIRS_003',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
});

// Define map.
const map = L.map('map', {
  crs: L.CRS.EPSG4326, // WGS 84
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
