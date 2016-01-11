"use strict";

// NOTE: the following global variables need to be set prior to loading this script:
// * geoserver_wms_url
// * geocoder_url
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
        // "PRS styled" internal version of cadastre below.
        crs: L.CRS.EPSG4326,
        layers: 'cddp:cadastre_prs',
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
    // Internal DPaW geocoding service.
    url: geocoder_url + '?q={s}&limit=5',
    propertyName: 'address',
    // Below is the OSM Noninatum geocoder URL.
    //url: 'http://nominatim.openstreetmap.org/search?format=json&q={s}',
    //propertyName: 'display_name',
    propertyLoc: ['lat','lon'],
    delayType: 1000,
    textErr: '',
    zoom: 17,
    circleLocation: true,
    autoCollapse: true
}));
