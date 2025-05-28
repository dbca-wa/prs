'use strict';
// NOTE: some global constants are defined in the base template context.

// A small function to add a hashcode function to String
// Ref: http://werxltd.com/wp/2010/05/13/javascript-implementation-of-javas-string-hashcode-method/
String.prototype.hashCode = function () {
  let hash = 0;
  if (this.length == 0) return hash;
  for (let i = 0; i < this.length; i++) {
    const char = this.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash); // Always return absolute value.
};

// GeoJSON layer to store clicked-on cadastre locations.
const newLocationsLayer = L.geoJSON(null, {}).addTo(map);

let locations_count = 0;
let locationsSelected = {};
let clickChooseEnabled = true;

// Function to add a prefilled, hidden form fieldset.
const addFormFieldset = function (feature) {
  locations_count += 1;
  const obj = feature.properties;
  const fid = feature.id;
  let address = '';
  let addrs_no = '';
  let road_name = '';
  let road_sfx = '';
  let locality = '';
  let postcode = '';

  if (obj.CAD_LOT_NUMBER) {
    address += `Lot ${obj.CAD_LOT_NUMBER} `;
  }
  if (obj.CAD_HOUSE_NUMBER) {
    address += `${obj.CAD_HOUSE_NUMBER} `;
    addrs_no = obj.CAD_HOUSE_NUMBER;
  }
  if (obj.CAD_ROAD_NAME) {
    address += `${obj.CAD_ROAD_NAME} `;
    road_name = obj.CAD_ROAD_NAME;
  }
  if (obj.CAD_ROAD_TYPE) {
    address += `${obj.CAD_ROAD_TYPE} `;
    road_sfx = obj.CAD_ROAD_TYPE;
  }
  if (obj.CAD_LOCALITY) {
    address += `${obj.CAD_LOCALITY} `;
    locality = obj.CAD_LOCALITY;
  }
  if (obj.CAD_POSTCODE) {
    address += `${obj.CAD_POSTCODE}`;
    postcode = obj.CAD_POSTCODE;
  }

  // Construct the fieldset text.
  const fieldset = `<fieldset id="fieldset_${fid}" class="form-inline" style="display:none;">
  <input name="form-${locations_count}-address_no" class="form-control" value="${addrs_no}">
  <input name="form-${locations_count}-road_name" class="form-control" value="${road_name}">
  <input name="form-${locations_count}-road_suffix" class="form-control" value="${road_sfx}">
  <input name="form-${locations_count}-locality" class="form-control" value="${locality}">
  <input name="form-${locations_count}-postcode" class="form-control" value="${postcode}">
  <input name="form-${locations_count}-wkt" class="form-control" value="${wellknown.stringify(feature)}">
</fieldset>`;
  // Finally, prepend the fieldset to the form.
  $('form#locations_form').prepend(fieldset);

  return address;
};

// Function to query Geoserver for the clicked-on location, return a feature and add it to newLocationsLayer.
const queryCadastre = function (latlng) {
  if (latlng == null) {
    return;
  }
  // Generate our CQL filter.
  const filter = `INTERSECTS(SHAPE, POINT (${latlng.lat} ${latlng.lng}))`;
  $.ajax({
    url: context.cadastre_query_url,
    data: { cql_filter: filter },
    dataType: 'json',
    success: function (data) {
      // Add the first feature returned by the query to newLocationsLayer.
      const fid = data.features[0]['id'];
      const feature = L.geoJson(data.features[0]);
      locationsSelected[fid] = feature;
      feature.addTo(newLocationsLayer);
      // Add a form fieldset containing the feature data.
      const address = addFormFieldset(data.features[0]);
      // Insert the address line as a <li> element.
      const li = `<li><button type='button' class='btn btn-danger btn-xs removeFeature' data-feature-id='${fid}'>Remove</button> ${address}</li>`;
      $('ol#selected_locations').append(li);
    },
  });
};
const removeFeature = function (newLocationsLayer, featureId) {
  delete locationsSelected[featureId];
  newLocationsLayer.clearLayers();
  for (const key in locationsSelected) {
    const location = locationsSelected[key];
    location.addTo(newLocationsLayer);
  }
};

// Add a FeatureGroup to contain draw features.
const drawnFeatures = new L.FeatureGroup();
map.addLayer(drawnFeatures);

// Add a draw control to the map.
const drawControl = new L.Control.Draw({
  position: 'topleft',
  draw: {
    polygon: { allowIntersection: false, showArea: true },
    polyline: false,
    rectangle: false,
    circle: false,
    circlemarker: false,
    marker: false,
  },
  edit: {
    featureGroup: drawnFeatures,
    edit: false,
    remove: true,
  },
});
map.addControl(drawControl);

// Set draw:drawstart and draw:drawstop events to disable the 'click to select' function.
map.on('draw:drawstart', function (e) {
  // Disable 'click to choose location'.
  clickChooseEnabled = false;
});
map.on('draw:drawstop', function (e) {
  // Enable 'click to choose location'.
  clickChooseEnabled = true;
});
let layer;
let feature;
map.on('draw:created', function (e) {
  layer = e.layer;
  drawnFeatures.addLayer(layer);
  feature = layer.toGeoJSON();
  // Make the feature ID a hash of the wkt.
  feature.id = wellknown.stringify(feature).hashCode();
  addFormFieldset(feature);
});
map.on('draw:deleted', function (e) {
  const layers = e.layers; // Can delete multiple features (layers).
  layers.eachLayer(function (layer) {
    feature = layer.toGeoJSON();
    feature.id = wellknown.stringify(feature).hashCode();
    // Remove the hidden form fieldset.
    removeFormFieldset(feature.id);
  });
});

// Click event for the map - add clicked-on features to a list.
map.on('click', function (e) {
  // IE11 hack below: prevent the click if the lot search input has focus.
  if (clickChooseEnabled && !$('input#id_input_lotSearch').is(':focus')) {
    queryCadastre(e.latlng);
  }
});

const removeFormFieldset = function (featureId) {
  const fid = 'fieldset_{fid}'.replace('{fid}', featureId);
  // Use getElementById because fid messes with jQuery regex.
  const thing = $(document.getElementById(fid)).get(0);
  $(thing).remove(); // Because IE11 :/
};

// Click event for dynamically-generated "Remove" buttons.
$(document.body).on('click', 'button.removeFeature', function () {
  const featureId = $(this).data('feature-id');
  removeFeature(newLocationsLayer, featureId);
  // Remove the visible list element.
  const li = $(this).parent().get(0);
  $(li).remove(); // Because IE11 :/
  // Remove the hidden form fieldset.
  removeFormFieldset(featureId);
});
$('input#id_lotSearch').change(function () {
  const lotNo = $(this).val();
  findLot(lotNo);
});
