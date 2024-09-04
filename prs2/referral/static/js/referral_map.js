"use strict";
// NOTE: some global constants are set in the base template.
const geoserver_wmts_url = kmi_geoserver_url + "/gwc/service/wmts?service=WMTS&request=GetTile&version=1.0.0&tilematrixset=gda94&tilematrix=gda94:{z}&tilecol={x}&tilerow={y}&format=image/jpeg"

// Define baselayer tile layers.
const landgateOrthomosaic = L.tileLayer(
  geoserver_wmts_url + "&layer=landgate:virtual_mosaic",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const mapboxStreets = L.tileLayer(
  geoserver_wmts_url + "&layer=dbca:mapbox-streets",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const waCoast = L.tileLayer(
  geoserver_wmts_url + "&layer=public:wa_coast_pub",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);

// Define overlay tile layers.
// Cadastre uses KB as the source, not KMI.
const cadastre = L.tileLayer.wms(mapproxy_url, {
  layers: 'dbca-cadastre',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
  minZoom: 13,
});
// PRS uses WMS, being a "live" layer.
const prsLocations = L.tileLayer.wms(kmi_geoserver_url + "/ows", {
  layers: prs_layer_name,
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
});
const dbcaRegions = L.tileLayer(
  geoserver_wmts_url + "&layer=cddp:dbca_regions",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const dbcaTenure = L.tileLayer(
  geoserver_wmts_url + "&layer=cddp:dbca_managed_tenure",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const regionalParks = L.tileLayer(
  geoserver_wmts_url + "&layer=cddp:regional_parks",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const swanCannDevContArea = L.tileLayer(
  geoserver_wmts_url + "&layer=cddp:cpt_swan_cann_dev_cont_area",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const ucl = L.tileLayer(
  geoserver_wmts_url + "&layer=cddp:unallocated_crown_land",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const lgaBoundaries = L.tileLayer(
  geoserver_wmts_url + "&layer=cddp:local_gov_authority",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);

// Define map.
var map = L.map('map', {
  crs: L.CRS.EPSG4326,  // WGS 84
  center: [-31.96, 115.87],
  zoom: 16,
  minZoom: 6,
  maxZoom: 18,
  layers: [landgateOrthomosaic, cadastre],  // Sets default selections.
  attributionControl: false,
});

// Define layer groups.
var baseMaps = {
  "Landgate orthomosaic": landgateOrthomosaic,
  "Mapbox streets": mapboxStreets,
  "WA coast": waCoast,
};
var overlayMaps = {
  "Cadastre": cadastre,
  "PRS locations": prsLocations,
  "DBCA regions": dbcaRegions,
  "DBCA tenure": dbcaTenure,
  "Regional Parks": regionalParks,
  "Swan Canning Dev Ctrl Area": swanCannDevContArea,
  "Unallocated Crown Land": ucl,
  "LGA boundaries": lgaBoundaries,
};

// Define layer control.
L.control.layers(baseMaps, overlayMaps).addTo(map);

// Define scale bar
L.control.scale({ maxWidth: 500, imperial: false }).addTo(map);

function searchGeocoder(text, response) {
  // Use jQuery to query the Geocoder service API.
  return $.ajax({
    url: geocoder_url,
    data: { q: text },
    dataType: 'json',
    success: function (data) {
      response(data);
    }
  });
};

function filterGeocoderRecords(text, records) {
  // The stock leaflet-search function seemed to filter out all records from the response, so we override it.
  return records;
};

// Define geocoder search input.
map.addControl(new L.Control.Search({
  sourceData: searchGeocoder,
  filterData: filterGeocoderRecords,
  propertyName: 'address',
  propertyLoc: ['lat', 'lon'],
  // Other variables.
  delayType: 1000,
  textErr: '',
  zoom: 17,
  circleLocation: true,
  autoCollapse: true
}));

// Define a custom lot filtering form Control
L.Control.LotFilter = L.Control.extend({
  options: {
    position: "topleft",
    placeholder: "Highlight Lots in view"
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
    var input = L.DomUtil.create('input', className, this._container);
    input.type = 'text';
    input.value = '';
    input.placeholder = text;
    input.role = 'search';
    input.id = 'id_input_lotSearch';
    // Prevent click progration (handled differently in IE11)
    if (!(window.ActiveXObject) && "ActiveXObject" in window) {
      input.MSPointerDown = input.onmousedown = input.ondblclick = input.onpointerdown = L.DomEvent.stopPropagation;
    } else {
      L.DomEvent.disableClickPropagation(input);  // Prevents input selection in IE11.
    };

    return input;
  },
  submit: function (e) {
    L.DomEvent.preventDefault(e);
  }
});
L.control.lotfilter = function (id, options) {
  return new L.Control.LotFilter(id, options);
};
// Add the custom control to the map, then set a change() event listener on it
const lotFilter = new L.Control.LotFilter({});
map.addControl(lotFilter);
$("input#id_input_lotSearch").change(function () {
  var lotname = $(this).val().toUpperCase();
  if (lotname) {
    findLot(lotname);
  }
});

// Add a feature group to the map to contain filtered Lot boundaries.
var lotsearchresults = new L.featureGroup();
map.addLayer(lotsearchresults);

var findLot = function (lotname) {
  // Generate our CQL filter.
  var filter = "CAD_LOT_NUMBER like '%" + lotname + "%' AND BBOX(SHAPE," + map.getBounds().toBBoxString() + ",'EPSG:4326')";
  $.ajax({
    url: cadastre_query_url,
    data: { 'cql_filter': filter },
    dataType: 'json',
    success: function (data) {
      if (data.totalFeatures === 0 && map.getMinZoom() < map.getZoom() && confirm("Couldn't find Survey Lot containing '" + lotname + "' in viewport, zoom out and try again?")) {
        map.zoomOut();
        findLot(lotname);
      }
      if (data.totalFeatures > 0) {
        lotsearchresults.clearLayers();
        lotsearchresults.addLayer(L.geoJson(data, {
          color: '#fa00ff',
          clickable: false
        }));
        map.fitBounds(lotsearchresults.getBounds());
      }
    }
  });
};
// Log zoom level to console.
//map.on('zoomend', function (e) {console.log(e.target._zoom)});

// Add a fullscreen control to the map.
const fullScreen = new L.control.fullscreen();
map.addControl(fullScreen);
