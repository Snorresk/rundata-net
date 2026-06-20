import { isCompactDbLayout } from './index_layout.js';

/*
 This script assumes that you reference leaflet.js and leaflet.css in your HTML file.
 It allows relies on defined `isSafari` function.
*/

const MOBILE_PAIR_SPIDERFY_MAX_DISTANCE_METERS = 100;
const MOBILE_SHARED_COORDINATE_MAX_MARKERS = 10;

export function shouldSpiderfyNearbyPair(cluster, map, maxDistanceMeters = MOBILE_PAIR_SPIDERFY_MAX_DISTANCE_METERS) {
  if (!cluster || typeof cluster.getAllChildMarkers !== 'function'
    || !map || typeof map.distance !== 'function') {
    return false;
  }

  if (typeof cluster.getChildCount === 'function' && cluster.getChildCount() !== 2) {
    return false;
  }

  const childMarkers = cluster.getAllChildMarkers();
  if (childMarkers.length !== 2) {
    return false;
  }

  return map.distance(
    childMarkers[0].getLatLng(),
    childMarkers[1].getLatLng()
  ) <= maxDistanceMeters;
}

export function shouldSpiderfySharedCoordinates(cluster, maxMarkers = MOBILE_SHARED_COORDINATE_MAX_MARKERS) {
  if (!cluster || typeof cluster.getChildCount !== 'function'
    || typeof cluster.getAllChildMarkers !== 'function') {
    return false;
  }

  const childCount = cluster.getChildCount();
  if (childCount < 2 || childCount > maxMarkers) {
    return false;
  }

  const childMarkers = cluster.getAllChildMarkers();
  if (childMarkers.length !== childCount) {
    return false;
  }

  const firstLatLng = childMarkers[0].getLatLng();
  return childMarkers.every(marker => {
    const latLng = marker.getLatLng();
    return latLng.lat === firstLatLng.lat && latLng.lng === firstLatLng.lng;
  });
}

export function handleMobileClusterClick(event, map) {
  const cluster = event && event.layer;
  if (!cluster) {
    return;
  }

  if (shouldSpiderfyNearbyPair(cluster, map) || shouldSpiderfySharedCoordinates(cluster)) {
    cluster.spiderfy();
    return;
  }

  const isAtMaxZoom = typeof map.getZoom === 'function'
    && typeof map.getMaxZoom === 'function'
    && map.getZoom() >= map.getMaxZoom();
  if (isAtMaxZoom && typeof cluster.spiderfy === 'function') {
    cluster.spiderfy();
  } else if (typeof cluster.zoomToBounds === 'function') {
    cluster.zoomToBounds();
  }
}

export function getMarkerClusterOptions(isMobile) {
  const options = {
    showCoverageOnHover: true,
    chunkedLoading: true,
    maxClusterRadius: 60,
  };
  if (isMobile) {
    // Handle small nearby pairs ourselves so they separate immediately on tap.
    options.zoomToBoundsOnClick = false;
    options.spiderfyOnMaxZoom = false;
  }
  return options;
}

export function getSpiderfiedTooltipDirection(marker, cluster, map) {
  if (!marker || !cluster || !map
    || typeof marker.getLatLng !== 'function'
    || typeof cluster.getLatLng !== 'function'
    || typeof map.latLngToLayerPoint !== 'function') {
    return 'auto';
  }

  const markerPoint = map.latLngToLayerPoint(marker.getLatLng());
  const clusterPoint = map.latLngToLayerPoint(cluster.getLatLng());
  const deltaX = markerPoint.x - clusterPoint.x;
  const deltaY = markerPoint.y - clusterPoint.y;

  if (Math.abs(deltaX) >= Math.abs(deltaY)) {
    return deltaX >= 0 ? 'right' : 'left';
  }
  return deltaY >= 0 ? 'bottom' : 'top';
}

function getSpiderfyEventMarkers(event) {
  if (event && Array.isArray(event.markers)) {
    return event.markers;
  }
  if (event && event.cluster && typeof event.cluster.getAllChildMarkers === 'function') {
    return event.cluster.getAllChildMarkers();
  }
  return [];
}

export function positionSpiderfiedTooltips(event, map) {
  const cluster = event && event.cluster;
  if (!cluster) {
    return;
  }

  getSpiderfyEventMarkers(event).forEach(marker => {
    const tooltip = typeof marker.getTooltip === 'function' ? marker.getTooltip() : null;
    if (!tooltip || !tooltip.options) {
      return;
    }
    if (typeof tooltip._rundataOriginalDirection === 'undefined') {
      tooltip._rundataOriginalDirection = tooltip.options.direction || 'auto';
    }
    tooltip.options.direction = getSpiderfiedTooltipDirection(marker, cluster, map);
    if (typeof tooltip.update === 'function') {
      tooltip.update();
    }
  });
}

export function resetSpiderfiedTooltips(event) {
  getSpiderfyEventMarkers(event).forEach(marker => {
    const tooltip = typeof marker.getTooltip === 'function' ? marker.getTooltip() : null;
    if (!tooltip || !tooltip.options || typeof tooltip._rundataOriginalDirection === 'undefined') {
      return;
    }
    tooltip.options.direction = tooltip._rundataOriginalDirection;
    delete tooltip._rundataOriginalDirection;
    if (typeof tooltip.update === 'function') {
      tooltip.update();
    }
  });
}

// Initialize the map on the user-provided div with a given center and zoom level
// Default center is [56.607512, 16.439838] and default zoom is 8.
export function initMap(divId, center = [56.607512, 16.439838], zoom = 8) {
  const isMobile = isMobileDevice();
  const map = L.map(divId, {
    fullscreenControl: true,
    // Use pseudo-fullscreen only on mobile to avoid desktop behavior changes.
    fullscreenControlOptions: isMobile ? {
      forcePseudoFullscreen: true,
      pseudoFullscreen: true,
    } : {},
  }).setView(center, zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> contributors',
    referrerPolicy: 'origin',
  }).addTo(map);

  // add location control to global name space for testing only
  // on a production site, omit the "lc = "!
  L.control.locate({
    locateOptions: {
      enableHighAccuracy: true,
      timeout: 12000,
      maximumAge: 60000,
    },
    strings: {
      title: "My location",
    }
  })
  .addTo(map);

  map.on('locationerror', function(event) {
    const details = getGeoLocationErrorDetails(event);
    const message = `Geolocation error: ${details}`;
    if (typeof showAlert === 'function') {
      showAlert(message);
    } else {
      alert(message);
    }
  });

  const markers = L.markerClusterGroup(getMarkerClusterOptions(isMobile));
  markers.on('click', function (e) {
    scrollToInscription(e.layer.options.signature, e.layer.options.id);
  });
  if (isMobile) {
    markers.on('clusterclick', function(event) {
      handleMobileClusterClick(event, map);
    });
    markers.on('spiderfied', function(event) {
      positionSpiderfiedTooltips(event, map);
    });
    markers.on('unspiderfied', resetSpiderfiedTooltips);
  }
  markers.addTo(map);

  return {map, markers};
}

function getGeoLocationErrorDetails(event) {
  const code = event && typeof event.code === 'number' ? event.code : null;
  const browserMessage = event && event.message ? String(event.message) : '';

  if (code === 1) {
    return 'permission denied. Allow location access for this site in browser settings and reload.';
  }
  if (code === 2) {
    return 'position unavailable. Check GPS/network and try again.';
  }
  if (code === 3) {
    return 'timeout. Move to better coverage and try again.';
  }

  if (browserMessage) {
    return browserMessage;
  }
  return 'unknown issue. Check site permission and connection, then try again.';
}

export function onHideMapClicked(mapContainerId, menuItemId) {
  const mapContainerJquery = `#${mapContainerId}`;
  const menuItemJquery = `#${menuItemId}`;

  $(mapContainerJquery).toggle();
  if ($(mapContainerJquery).is(":visible")) {
    $(menuItemJquery).html('Hide map');
  } else {
    $(menuItemJquery).html('Show map');
  }
}

function isMobileDevice() {
  return isCompactDbLayout();
}

function getGeoIntentURL(lat, lng) {
  // Use Google Maps universal directions URL so mobile users (including iPhone)
  // can open navigation consistently.
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`;
}

function selectInscriptionForMobileInfo(inscriptionId) {
  if (typeof window === 'undefined') {
    return false;
  }

  if (typeof window.scrollToInscription === 'function') {
    window.scrollToInscription('', inscriptionId);
    return true;
  }

  const jquery = window.jQuery || window.$;
  if (typeof jquery !== 'function') {
    return false;
  }
  const tree = jquery('#jstree').jstree(true);
  if (!tree) {
    return false;
  }
  tree.deselect_all();
  tree.select_node(String(inscriptionId));
  return true;
}

export function openMobileInscriptionInfo(inscriptionId) {
  if (!isMobileDevice() || !selectInscriptionForMobileInfo(inscriptionId)) {
    return false;
  }

  const infoButton = typeof document !== 'undefined'
    ? document.getElementById('mobilePaneInfo')
    : null;
  if (infoButton && typeof infoButton.click === 'function') {
    infoButton.click();
  }
  return false;
}

function isLostInscription(inscriptionData) {
  const value = inscriptionData && inscriptionData.lost;
  if (value === true || value === 1 || value === '1') {
    return true;
  }
  return false;
}

function hasCurrentLocationInfo(inscriptionData) {
  const currentLocation = inscriptionData && inscriptionData.current_location;
  return String(currentLocation || '').trim().length > 0;
}

function makeMobileTooltipOpenPopup(marker, tooltip) {
  const tooltipElement = tooltip && typeof tooltip.getElement === 'function'
    ? tooltip.getElement()
    : null;
  if (!tooltipElement || tooltipElement.dataset.mobilePopupTrigger === 'true') {
    return;
  }

  tooltipElement.dataset.mobilePopupTrigger = 'true';
  tooltipElement.setAttribute('role', 'button');
  tooltipElement.setAttribute('tabindex', '0');
  tooltipElement.setAttribute('aria-label', 'Open Drive here and warnings');

  const openPopupFromTooltip = (event) => {
    if (event && typeof event.preventDefault === 'function') {
      event.preventDefault();
    }
    if (event && typeof event.stopPropagation === 'function') {
      event.stopPropagation();
    }
    marker.openPopup();
  };

  tooltipElement.addEventListener('click', openPopupFromTooltip);
  tooltipElement.addEventListener('touchend', openPopupFromTooltip);
  tooltipElement.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      openPopupFromTooltip(event);
    }
  });
}

function inscription2marker(inscriptionData, lat, lon, locationType = 'found', leaflet=L) {
  // Inscriptions have two sets of latitude and longitude values: one for the
  // original location and one for the present location. We will always create two
  // markers for each inscription. This means that even if the present location is
  // the same as the original location, we will still create two markers.

  if (lat === 0.0 || lon === 0.0) {
    return null;
  }
  let marker = leaflet.marker([lat, lon], {
    signature: inscriptionData.signature_text,
    id: inscriptionData.id,
  });
  let popupText = `${inscriptionData.signature_text}<br>`;
  const isMobile = isMobileDevice();
  const hasCurrentLocation = hasCurrentLocationInfo(inscriptionData);
  const warningTexts = [];
  const infoTexts = [];
  const confirmTexts = [];
  if (isLostInscription(inscriptionData)) {
    warningTexts.push('Warning: this inscription is lost.');
    confirmTexts.push('Are you sure you want to drive here? The inscription is lost!');
  }
  if (locationType === 'found' && hasCurrentLocation) {
    warningTexts.push('Warning: this inscription is moved.');
  }
  if (isMobile && locationType === 'present' && hasCurrentLocation) {
    warningTexts.push('Warning: this inscription is moved.');
    infoTexts.push('You are driving to Current location.');
  }
  if (locationType === 'found' && hasCurrentLocation) {
    confirmTexts.push('Are you sure you want to drive to Found location? The inscription is moved! Check its current location.');
  }
  warningTexts.forEach(text => {
    if (isMobile) {
      popupText += `<span class="map-popup-warning">${text}</span><br>`;
    } else {
      popupText += `<span style="color:#b94a48;font-weight:600;">${text}</span><br>`;
    }
  });
  infoTexts.forEach(text => {
    popupText += `<span class="map-popup-note">${text}</span><br>`;
  });
  const destinationUrl = getGeoIntentURL(lat, lon);
  const driveLinkClass = isMobile ? ' class="map-drive-link"' : '';
  if (confirmTexts.length > 0) {
    const confirmText = confirmTexts.join('\n');
    popupText += `<a${driveLinkClass} href="${destinationUrl}" target="_self" onclick="return window.confirm('${confirmText}')">Drive here!</a>`;
  } else {
    popupText += `<a${driveLinkClass} href="${destinationUrl}" target="_self">Drive here!</a>`;
  }
  if (isMobile) {
    const inscriptionId = JSON.stringify(String(inscriptionData.id));
    popupText += `<button type="button" class="map-open-info-link" onclick='return window.openMobileInscriptionInfo(${inscriptionId})'>Open info</button>`;
  }
  // Tooltip is simple and is always on, popup supports HTML and is opened  /closed by user
  const popupOptions = isMobile
    ? {
        autoClose: false,
        autoPan: true,
        closeButton: true,
        maxWidth: 260,
      }
    : {autoClose: false};
  marker.bindPopup(popupText, popupOptions);
  const tooltipOptions = isMobile
    ? {permanent: true, interactive: true, className: 'mobile-map-id-tooltip'}
    : {permanent: true};
  marker.bindTooltip(inscriptionData.signature_text, tooltipOptions).openTooltip();
  if (isMobile && typeof marker.on === 'function') {
    marker.on('tooltipopen', (event) => {
      makeMobileTooltipOpenPopup(marker, event.tooltip);
    });
  }
  if (isMobile && typeof marker.getTooltip === 'function') {
    makeMobileTooltipOpenPopup(marker, marker.getTooltip());
  }

  return marker;
}

/**
 * Converts inscription data to map markers and returns a collection of markers.
 *
 * @param {Map} dbMap - A map containing inscription data with keys as unique identifiers.
 * @param {Object} [leaflet=L] - The Leaflet library instance to use for creating markers.
 * @returns {Map} A map where each key corresponds to an inscription and the value is an object
 *                containing 'found' and 'present' markers. The key is the same as in dbMap.
 */
export function inscriptions2markers(dbMap, leaflet=L) {
  const mapMarkers = new Map(); // Collection of all created map markers. This is used
  // in order to create markers only once.

  dbMap.forEach((inscriptionData, key) => {
    const signatureName = inscriptionData.signature_text;

    const found_lat = parseFloat(inscriptionData.latitude) || 0.0;
    const found_lon = parseFloat(inscriptionData.longitude) || 0.0;
    const present_lat = parseFloat(inscriptionData.present_latitude) || 0.0;
    const present_lon = parseFloat(inscriptionData.present_longitude) || 0.0;
    const marker_found = inscription2marker(inscriptionData, found_lat, found_lon, 'found', leaflet);
    if (!marker_found) {
      return;
    }
    if (!mapMarkers.has(key)) {
      mapMarkers.set(key, {found: null, present: null});
    }
    mapMarkers.get(key).found = marker_found;

    const marker_present = inscription2marker(inscriptionData, present_lat, present_lon, 'present', leaflet);
    mapMarkers.get(key).present = marker_present ? marker_present : marker_found;
  });
  return mapMarkers;
}


/**
 * Displays markers on the map based on the provided parameters.
 *
 * @param {Object} options - The options for displaying markers.
 * @param {boolean} [options.preserveMapArea=false] - If true, the map area will not be adjusted to fit the markers.
 * @param {boolean} [options.showOriginalLocation=false] - If true, markers will be shown for the original (found) location of inscriptions, otherwise for the present location.
 * @param {Array<string>} [options.inscriptionIds=[]] - An array of inscription IDs to display markers for.
 * @param {Map<string, Object>} [options.allMarkers=new Map()] - A map containing all markers, keyed by inscription ID.
 * @param {Object} [options.mapObject=null] - The Leaflet map object.
 * @param {Object} [options.markersLayer=null] - The Leaflet layer group to which markers will be added.
 */
export function showMarkers({
  preserveMapArea = false,
  showOriginalLocation = false,
  inscriptionIds = [],
  allMarkers = new Map(),
  mapObject = null,
  markersLayer = null,
} = {}) {
  // array of all marker's lat/lon. Used to calculate new bounds.
  let markersLatLon = [];

  if (!markersLayer || !mapObject) {
    console.log('No markers layer or map object provided');
    return;
  }

  // clear any markers from the map
  markersLayer.clearLayers();

  for (let i = 0; i < inscriptionIds.length; i++) {
    const key = inscriptionIds[i];
    if (!allMarkers.has(key)) {
      continue;
    }
    const inscriptionMarkers = allMarkers.get(key);
    const markerToShow = showOriginalLocation ? inscriptionMarkers.found : inscriptionMarkers.present;
    markersLayer.addLayers(markerToShow);
    markersLatLon.push(markerToShow.getLatLng());
  }

  if (markersLatLon.length > 0 && !preserveMapArea) {
    if (typeof mapObject.invalidateSize === 'function') {
      mapObject.invalidateSize({pan: false});
    }
    mapObject.fitBounds(markersLatLon, {padding: [20, 20]});
  }
}
