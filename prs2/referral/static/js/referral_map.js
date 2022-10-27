"use strict";

// NOTE: the following global variables need to be set prior to loading this script:
// * geoserver_wmts_url
// * cddp_geoserver_wmts_url
// * geoserver_wfs_url
// * cddp_geoserver_wfs_url
// * geoserver_basic_auth
// * geocoder_url

// Define baselayer tile layers.
const landgateOrthomosaic = L.tileLayer(
  geoserver_wmts_url + "?service=WMTS&request=GetTile&version=1.0.0&tilematrixset=gda94&TileMatrix=gda94:{z}&TileCol={x}&TileRow={y}&format=image/png&layer=landgate:virtual_mosaic",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const mapboxStreets = L.tileLayer(
  geoserver_wmts_url + "?service=WMTS&request=GetTile&version=1.0.0&tilematrixset=gda94&TileMatrix=gda94:{z}&TileCol={x}&TileRow={y}&format=image/png&layer=dbca:mapbox-streets",
  {
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const emptyBaselayer = L.tileLayer();

// Define overlay tile layers.
const cadastre = L.tileLayer(
  cddp_geoserver_wmts_url + "?layer=cddp:cpt_cadastre_scdb&style=cddp:state_cadastre_lot_no&tilematrixset=EPSG:4326&Service=WMTS&Request=GetTile&Version=1.0.0&Format=image/png&TileMatrix=EPSG:4326:{z}&TileCol={x}&TileRow={y}",
  {
    opacity: 0.85,
    //tileSize: 1024,
    //zoomOffset: -2,
  },
);
const slipRoads = L.tileLayer(
  geoserver_wmts_url + "?service=WMTS&request=GetTile&version=1.0.0&tilematrixset=gda94&TileMatrix=gda94:{z}&TileCol={x}&TileRow={y}&format=image/png&transparent=true&layer=landgate:roads_slip",
  {
    opacity: 0.75,
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const prsLocations = L.tileLayer(
  geoserver_wmts_url + "?service=WMTS&request=GetTile&version=1.0.0&tilematrixset=gda94&TileMatrix=gda94:{z}&TileCol={x}&TileRow={y}&format=image/png&transparent=true&layer=dbca:prs_locations_view",
  {
    opacity: 0.75,
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const dbcaTenure = L.tileLayer(
  geoserver_wmts_url + "?service=WMTS&request=GetTile&version=1.0.0&tilematrixset=gda94&TileMatrix=gda94:{z}&TileCol={x}&TileRow={y}&format=image/png&transparent=true&layer=cddp:legislated_lands_and_waters",
  {
    opacity: 0.75,
    tileSize: 1024,
    zoomOffset: -2,
  },
);
const regionalParks = L.tileLayer(
  geoserver_wmts_url + "?service=WMTS&request=GetTile&version=1.0.0&tilematrixset=gda94&TileMatrix=gda94:{z}&TileCol={x}&TileRow={y}&format=image/png&transparent=true&layer=landgate:DBCA-026",
  {
    opacity: 0.75,
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
});

// Define layer groups.
var baseMaps = {
    "Landgate orthomosaic": landgateOrthomosaic,
    "Mapbox streets": mapboxStreets,
    "No base layer": emptyBaselayer,
};
var overlayMaps = {
    "Cadastre": cadastre,
    "SLIP roads": slipRoads,
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
    headers: {Authorization: 'Basic ' + geoserver_basic_auth},
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
        // Test if the search term starts with 'LOT'; if not, append this.
        if (!lotname.startsWith('LOT')) {
          lotname = 'LOT ' + lotname;
        }
        findLot(lotname);
    }
});

// Add a feature group to the map to contain filtered Lot boundaries.
var lotsearchresults = new L.featureGroup();
map.addLayer(lotsearchresults);

// Define WFS layer for querying.
var cadastreWFSParams = {
    service: 'WFS',
    version: '2.0.0',
    request: 'GetFeature',
    typeName: 'cddp:cadastre',
    outputFormat: 'application/json',
    //typeName: 'cddp:cpt_cadastre_scdb',
    //outputFormat: 'text/javascript',
    //format_options: 'callback: getJson',
};

var findLot = function(lotname) {
    // Generate our CQL filter.
    var filter = "survey_lot like '%" + lotname + "%' AND BBOX(wkb_geometry," + map.getBounds().toBBoxString() + ",'EPSG:4326')";
    //var filter = "cad_lot_number like '%" + lotname + "%' AND BBOX(shape," + map.getBounds().toBBoxString() + ",'EPSG:4326')";
    var parameters = L.Util.extend(cadastreWFSParams, {'cql_filter': filter});
    $.ajax({
        url: geoserver_wfs_url,
        data: parameters,
        type: "GET",
        headers: {Authorization: 'Basic ' + geoserver_basic_auth},
        dataType: "json",
        //dataType: "jsonp",
        //jsonpCallback: "getJson",
        success: function(data) {
            if (data.totalFeatures === 0 && map.getMinZoom() < map.getZoom() && confirm("Couldn't find Lot " + lotname + " in viewport, zoom out and try again?")) {
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
