"use strict";
// NOTE: some global variables are set in the base template.

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
    var obj = feature.properties;
    var fid = feature.id;
    // Construct a form fieldset to submit the location.
    var address = '';
    var fieldset = '<fieldset id="fieldset_{fid}" class="form-inline" style="display:none;">' +
        '<input name="form-{0}-address_no" class="form-control" value="{addrs_no}">' +  // Address no.
        '<input name="form-{0}-road_name" class="form-control" value="{road_name}">' +  // Road
        '<input name="form-{0}-road_suffix" class="form-control" value="{road_sfx}">' +  // Road type suffix
        '<input name="form-{0}-locality" class="form-control" value="{locality}">' +  // Locality
        '<input name="form-{0}-postcode" class="form-control" value="{postcode}">' +  // Postcode
        '<input name="form-{0}-wkt" class="form-control" value="{wkt}">' +  // WKT
        '</fieldset>';
    fieldset = fieldset.replace('{fid}', fid);
    if (obj.CAD_LOT_NUMBER) {address += 'Lot ' + obj.CAD_LOT_NUMBER + ', '};
    if (obj.CAD_HOUSE_NUMBER) {
        address += obj.CAD_HOUSE_NUMBER;
        fieldset = fieldset.replace('{addrs_no}', obj.CAD_HOUSE_NUMBER);
    } else {
        fieldset = fieldset.replace('{addrs_no}', '');
    }
    if (address != '') {address += ' '};
    if (obj.CAD_ROAD_NAME) {
        address += obj.CAD_ROAD_NAME + ' ';
        fieldset = fieldset.replace('{road_name}', obj.CAD_ROAD_NAME);
    } else {
        fieldset = fieldset.replace('{road_name}', '');
    }
    if (obj.CAD_ROAD_TYPE) {
        address += obj.CAD_ROAD_TYPE + ' ';
        fieldset = fieldset.replace('{road_sfx}', obj.CAD_ROAD_TYPE);
    } else {
        fieldset = fieldset.replace('{road_sfx}', '');
    }
    if (obj.CAD_LOCALITY) {
        address += obj.CAD_LOCALITY + ' ';
        fieldset = fieldset.replace('{locality}', obj.CAD_LOCALITY);
    } else {
        fieldset = fieldset.replace('{locality}', '');
    }
    if (obj.CAD_POSTCODE) {
        address += obj.CAD_POSTCODE;
        fieldset = fieldset.replace('{postcode}', obj.CAD_POSTCODE);
    } else {
        fieldset = fieldset.replace('{postcode}', '');
    }
    // Insert WKT into the form.
    fieldset = fieldset.replace('{wkt}', wellknown.stringify(feature));
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
    // Generate our CQL filter.
    var filter = 'INTERSECTS(SHAPE, POINT ({0} {1}))'.replace('{0}', latlng.lat).replace('{1}', latlng.lng);
    $.ajax({
        url: cadastre_query_url,
        data: {'cql_filter': filter},
        dataType: 'json',
        success: function(data) {
            // Add the first feature returned by the query to locationsLayer.
            var fid = data.features[0]['id'];
            var feature = L.geoJson(data.features[0]);
            locationsSelected[fid] = feature;
            feature.addTo(locationsLayer);
            // Add a form fieldset containing the feature data.
            var address = addFormFieldset(data.features[0]);
            // Insert the address line as a <li> element.
            var li = "<li><button type='button' class='btn btn-danger btn-xs removeFeature' data-feature-id='{}'>Remove</button> " + address + "</li>";
            li = li.replace('{}', data.features[0]['id']);
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
