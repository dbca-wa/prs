"use strict";

// NOTE: the following global variables need to be set prior to loading this script:
// * geoserver_wms_url
// * geoserver_wfs_url
// Define tile layers.
var landgateOrthomosaic = L.tileLayer.wms(
    geoserver_wms_url,
    {
        crs: L.CRS.EPSG4326,
        layers: 'landgate:LGATE-V001',
        tileSize: 1024,
        format: 'image/jpeg',
        tiled: true,
        version: '1.1.1'
    }
);
var mapboxSatellite = L.tileLayer.wms(
    geoserver_wms_url,
    {
        crs: L.CRS.EPSG4326,
        layers: 'dpaw:mapbox_satellite',
        tileSize: 1024,
        format: 'image/jpeg',
        tiled: true,
        version: '1.1.1'
    }
);
var mapboxStreets = L.tileLayer.wms(
    geoserver_wms_url,
    {
        crs: L.CRS.EPSG4326,
        layers: 'dpaw:mapbox_streets',
        tileSize: 1024,
        format: 'image/jpeg',
        tiled: true,
        version: '1.1.1'
    }
);
var cadastre = L.tileLayer.wms(
    geoserver_wms_url,
    {
        crs: L.CRS.EPSG4326,
        // Landgate-published cadastre:
        //layers: 'landgate:LGATE-001',
        // "PRS styled" internal version of cadastre:
        layers: 'cddp:cadastre',
        styles: 'cddp:cadastre.cadastre_prs',
        tileSize: 1024,
        format: 'image/png',
        tiled: true,
        transparent: true,
        version: '1.1.1'
    }
);
var prsLocations = L.tileLayer.wms(
    geoserver_wms_url,
    {
        crs: L.CRS.EPSG4326,
        layers: 'dpaw:prs_locations',
        opacity: 0.75,
        tileSize: 1024,
        format: 'image/png',
        tiled: true,
        transparent: true,
        version: '1.1.1'
    }
);

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
    "Landgate Orthomosaic": landgateOrthomosaic,
    "Mapbox Satellite": mapboxSatellite,
    "OpenStreetMap Streets": mapboxStreets
};
var overlayMaps = {
    "Cadastre": cadastre,
    "PRS locations": prsLocations,
};

// Define layer control.
L.control.layers(baseMaps, overlayMaps).addTo(map);

// Define scale bar
L.control.scale({maxWidth: 500, imperial: false}).addTo(map);

// Define geocoder search input.
map.addControl(new L.Control.Search({
    // OSM Noninatum geocoder URL
    // Limit searches to AU, and append "WA" to the end of every search :)
    url: '//nominatim.openstreetmap.org/search?format=json&countrycodes=au&q={s}%20western%20australia',
    propertyName: 'display_name',
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
    $.ajax({
        url: geoserver_wfs_url,
        data: {
            service: "WFS",
            version: "2.0.0",
            request: "GetFeature",
            typeName: "cddp:cadastre",
            outputFormat: "application/json",
            cql_filter: "survey_lot like '%"+lotname+"%' AND BBOX(wkb_geometry," + map.getBounds().toBBoxString() + ",'EPSG:4326')"
        },
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
