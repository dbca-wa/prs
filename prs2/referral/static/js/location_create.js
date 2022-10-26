"use strict";

// NOTE: the following global variables need to be set prior to loading this script:
// * geoserver_basic_auth

// A small function to add a hashcode function to String
// Ref: http://werxltd.com/wp/2010/05/13/javascript-implementation-of-javas-string-hashcode-method/
String.prototype.hashCode = function(){
    var hash = 0;
    if (this.length == 0) return hash;
    for (var i = 0; i < this.length; i++) {
        var char = this.charCodeAt(i);
        var hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
    }
    return Math.abs(hash);  // Always return absolute value.
}

// GeoJSON layer to store clicked-on cadastre locations.
var locationsLayer = L.geoJson();
locationsLayer.addTo(map);
var locations_count = 0;
var locationsSelected = {};
var clickChooseEnabled = true;

// Function to add a form fieldset.
var addFormFieldset = function(feature) {
    var fid = feature.object_id;
    // Construct a form fieldset to submit the location.
    var address = '';
    var fieldset = '<fieldset id="fieldset_{fid}" class="form-inline" style="display:none;">' +
        '<input name="form-{0}-address_no" class="form-control" value="{addrs_no}">' +  // Address no.
        '<input name="form-{0}-road_name" class="form-control" value="{road_name}">' +  // Road
        '<input name="form-{0}-road_suffix" class="form-control" value="{road_sfx}">' +  // Suffix
        '<input name="form-{0}-locality" class="form-control" value="{locality}">' +  // Locality
        '<input name="form-{0}-postcode" class="form-control" value="{postcode}">' +  // Postcode
        '<input name="form-{0}-wkt" class="form-control" value="{wkt}">' +  // WKT
        '</fieldset>';
    fieldset = fieldset.replace('{fid}', fid);
    if (feature.data.lot_number) {address += 'Lot ' + feature.data.lot_number + ', '};
    if (feature.data.house_number) {
        address += feature.data.house_number;
        fieldset = fieldset.replace('{addrs_no}', feature.data.house_number);
    } else {
        fieldset = fieldset.replace('{addrs_no}', '');
    }
    if (address != '') {address += ' '};
    if (feature.data.road_name) {
        address += feature.data.road_name + ' ';
        fieldset = fieldset.replace('{road_name}', feature.data.road_name);
    } else {
        fieldset = fieldset.replace('{road_name}', '');
    }
    if (feature.data.road_type) {
        address += feature.data.road_type + ' ';
        fieldset = fieldset.replace('{road_sfx}', feature.data.road_type);
    } else {
        fieldset = fieldset.replace('{road_sfx}', '');
    }
    if (feature.data.locality) {
        address += feature.data.locality + ' ';
        fieldset = fieldset.replace('{locality}', feature.data.locality);
    } else {
        fieldset = fieldset.replace('{locality}', '');
    }
    if (feature.data.postcode) {
        address += feature.data.postcode;
        fieldset = fieldset.replace('{postcode}', feature.data.postcode);
    } else {
        fieldset = fieldset.replace('{postcode}', '');
    }
    // Insert WKT into the form.
    fieldset = fieldset.replace('{wkt}', feature.boundary);
    // Make form input names unique.
    locations_count += 1;
    fieldset = fieldset.replace(/\{0\}/g, locations_count.toString());
    $("form#locations_form").prepend(fieldset);

    return address;
};

// Function to query Geoserver for the clicked-on location, return a feature and add it to locationsLayer.
var queryCadastre = function(latlng) {
    if (latlng == null) {
        return;
    }
    $.ajax({
      url: geocoder_url,
      data: {point: "{0},{1}".replace("{0}", latlng.lng).replace("{1}", latlng.lat)},
      type: "GET",
      dataType: "json",
      headers: {Authorization: 'Basic ' + geoserver_basic_auth},
      success: function(data) {
        var fid = data.object_id;
        var feature = wellknown.parse(data.boundary);
        var location = L.geoJson(feature);
        locationsSelected[fid] = location;
        location.addTo(locationsLayer);
        // Add a form fieldset containing the location data.
        var address = addFormFieldset(data);
        // Insert the address line as a <li> element.
        var li = "<li><button type='button' class='btn btn-danger btn-xs removeFeature' data-feature-id='{}'>Remove</button> " + address + "</li>";
        li = li.replace('{}', data.object_id);
        $("ol#selected_locations").append(li);
      }
    });
}
var removeFeature = function(locationsLayer, featureId) {
    delete locationsSelected[featureId];
    locationsLayer.clearLayers();
    for (var key in locationsSelected) {
        var l = locationsSelected[key];
        l.addTo(locationsLayer);
    }
}

// Add a FeatureGroup to contain draw features.
var drawnFeatures = new L.FeatureGroup();
map.addLayer(drawnFeatures);

// Add a draw control to the map.
var drawControl = new L.Control.Draw({
    position: 'topleft',
    draw: {
        polygon: {allowIntersection: false, showArea: true},
        polyline: false,
        rectangle: false,
        circle: false,
        circlemarker: false,
        marker: false
    },
    edit: {
        featureGroup: drawnFeatures,
        edit: false,
        remove: true
    }
});
map.addControl(drawControl);

// Set draw:drawstart and draw:drawstop events to disable the 'click to select' function.
map.on('draw:drawstart', function(e) {
    // Disable 'click to choose location'.
    clickChooseEnabled = false;
});
map.on('draw:drawstop', function(e) {
    // Enable 'click to choose location'.
    clickChooseEnabled = true;
});
var layer;
var feature;
map.on('draw:created', function (e) {
    layer = e.layer;
    drawnFeatures.addLayer(layer);
    feature = layer.toGeoJSON();
    // Make the feature ID a hash of the wkt.
    feature.id = wellknown.stringify(feature).hashCode();
    addFormFieldset(feature);
});
map.on('draw:deleted', function (e) {
    layers = e.layers;  // Can delete multiple features (layers).
    layers.eachLayer(function(layer) {
        feature = layer.toGeoJSON();
        feature.id = wellknown.stringify(feature).hashCode();
        // Remove the hidden form fieldset.
        removeFormFieldset(feature.id);
    });
});

// Click event for the map - add clicked-on features to a list.
map.on('click', function(e) {
    // IE11 hack below: prevent the click if the lot search input has focus.
    if (clickChooseEnabled && !$('input#id_input_lotSearch').is(":focus")) {
        queryCadastre(e.latlng);
    }
});

var removeFormFieldset = function(featureId) {
    var fid = "fieldset_{fid}".replace("{fid}", featureId);
    // Use getElementById because fid messes with jQuery regex.
    var thing = $(document.getElementById(fid)).get(0);
    $(thing).remove();  // Because IE11 :/
};

// Click event for dynamically-generated "Remove" buttons.
$(document.body).on('click', 'button.removeFeature', function() {
    var featureId = $(this).data('feature-id');
    removeFeature(locationsLayer, featureId);
    // Remove the visible list element.
    var li = $(this).parent().get(0);
    $(li).remove();  // Because IE11 :/
    // Remove the hidden form fieldset.
    removeFormFieldset(featureId);
});
$("input#id_lotSearch").change(function() {
    var lotNo = $(this).val();
    findLot(lotNo);
});
