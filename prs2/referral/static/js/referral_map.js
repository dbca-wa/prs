"use strict";
// NOTE: some global variables are set in the base template.

// Define baselayer tile layers.
const landgateOrthomosaic = L.tileLayer.wms(mapproxy_url, {
  layers: 'virtual-mosaic',
  tileSize: 1024,
  zoomOffset: -2,
});
const mapboxStreets = L.tileLayer.wms(mapproxy_url, {
  layers: 'mapbox-streets',
  format: 'image/png',
  tileSize: 1024,
  zoomOffset: -2,
});
const waCoast = L.tileLayer.wms(mapproxy_url, {
  layers: 'wa-coast',
  format: 'image/png',
  tileSize: 1024,
  zoomOffset: -2,
});

// Define overlay tile layers.
const cadastre = L.tileLayer.wms(mapproxy_url, {
  layers: 'dbca-cadastre',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
  tileSize: 1024,
  zoomOffset: -2,
  minZoom: 12,
});
const prsLocations = L.tileLayer.wms(prs_geoserver_url, {
  layers: 'prs:prs_locations_view',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
  tileSize: 256,
  zoomOffset: 0,
});
const dbcaTenure = L.tileLayer.wms(mapproxy_url, {
  layers: 'dbca-tenure',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
  tileSize: 1024,
  zoomOffset: -2,
});
const regionalParks = L.tileLayer.wms(mapproxy_url, {
  layers: 'dbca-regional-parks',
  format: 'image/png',
  transparent: true,
  opacity: 0.75,
  tileSize: 1024,
  zoomOffset: -2,
});

// Define map.
var map = L.map('map', {
    crs: L.CRS.EPSG4326,
    center: [-31.96, 115.87],
    zoom: 16,
    minZoom: 6,
    maxZoom: 18,
    layers: [landgateOrthomosaic, cadastre],  // Sets default selections.
});

// Define layer groups.
var baseMaps = {
    "Landgate orthomosaic": landgateOrthomosaic,
    "Mapbox streets": mapboxStreets,
    "WA coast": waCoast,
};
var overlayMaps = {
    "Cadastre": cadastre,
    //"SLIP roads": slipRoads,
    "PRS locations": prsLocations,
    "DBCA tenure": dbcaTenure,
    "Regional Parks": regionalParks,
};

// Define layer control.
L.control.layers(baseMaps, overlayMaps).addTo(map);

// Define scale bar
L.control.scale({maxWidth: 500, imperial: false}).addTo(map);

function searchGeocoder(text, response) {
  // Use jQuery to query the Geocoder service API.
  return $.ajax({
    url: geocoder_url,
    data: {q: text},
    dataType: 'json',
    success: function(data) {
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
  propertyLoc: ['lat','lon'],
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
    onAdd: function(map) {
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
    submit: function(e) {
        L.DomEvent.preventDefault(e);
    }
});
L.control.lotfilter = function(id, options) {
    return new L.Control.LotFilter(id, options);
};
// Add the custom control to the map, then set a change() event listener on it
map.addControl(new L.Control.LotFilter({}));
$("input#id_input_lotSearch").change(function() {
    var lotname = $(this).val().toUpperCase();
    if (lotname) {
        findLot(lotname);
    }
});

// Add a feature group to the map to contain filtered Lot boundaries.
var lotsearchresults = new L.featureGroup();
map.addLayer(lotsearchresults);

var findLot = function(lotname) {
    // Generate our CQL filter.
    var filter = "CAD_LOT_NUMBER like '%" + lotname + "%' AND BBOX(SHAPE," + map.getBounds().toBBoxString() + ",'EPSG:4326')";
    $.ajax({
        url: cadastre_query_url,
        data: {'cql_filter': filter},
        dataType: 'json',
        success: function(data) {
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
