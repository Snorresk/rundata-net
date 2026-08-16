import { isCompactDbLayout } from './index_layout.js';

/*
 This script assumes that you reference leaflet.js and leaflet.css in your HTML file.
 It allows relies on defined `isSafari` function.
*/

const MOBILE_PAIR_SPIDERFY_MAX_DISTANCE_METERS = 100;
const MOBILE_SHARED_COORDINATE_MAX_MARKERS = 10;
const PUBLICATION_MAP_WIDTH = 1200;
const PUBLICATION_MAP_HEIGHT = 900;
const PUBLICATION_MAP_MARGIN = {top: 82, right: 72, bottom: 92, left: 82};
const PUBLICATION_MAP_MIN_LAT_SPAN = 2.5;
const PUBLICATION_MAP_MIN_LON_SPAN = 3.5;
const PUBLICATION_MAP_TILE_SIZE = 256;
const PUBLICATION_MAP_OSM_MIN_ZOOM = 3;
const PUBLICATION_MAP_OSM_MAX_ZOOM = 14;
const PUBLICATION_MAP_OSM_MAX_TILES = 80;
const PUBLICATION_MAP_TILE_FETCH_CONCURRENCY = 8;
const PUBLICATION_MAP_TILE_FETCH_TIMEOUT_MS = 15000;
const PUBLICATION_MAP_TILE_PROVIDERS = {
  'carto-positron': {
    name: 'CARTO Positron',
    tileUrl: 'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors, © CARTO',
    caption: 'Map tiles © CARTO. Map data © OpenStreetMap contributors and available under the Open Database License: https://www.openstreetmap.org/copyright. Coordinates exported from Rundata-net. To publish or present this map, specify its source: https://rundata.info.',
  },
  osm: {
    name: 'OpenStreetMap Standard',
    tileUrl: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors',
    caption: 'Map tiles © OpenStreetMap contributors. Coordinates exported from Rundata-net. To publish or present this map, specify its source: https://rundata.info. OpenStreetMap data is available under the Open Database License: https://www.openstreetmap.org/copyright.',
  },
};

const PUBLICATION_MAP_LAND_POLYGONS = [
  {
    name: 'Scandinavia',
    points: [
      [4.9, 57.7], [5.2, 59.0], [4.9, 60.4], [5.8, 62.0], [6.6, 63.2],
      [8.1, 64.6], [10.3, 66.1], [12.4, 67.5], [14.4, 68.7], [17.0, 69.7],
      [20.1, 70.2], [23.8, 69.8], [26.8, 69.0], [29.7, 69.8], [31.3, 68.8],
      [30.8, 66.9], [29.4, 65.3], [29.9, 63.7], [29.1, 61.9], [27.2, 60.4],
      [24.6, 59.8], [22.1, 59.8], [19.8, 59.4], [18.5, 58.8], [17.8, 58.1],
      [16.2, 57.7], [15.3, 56.8], [13.9, 56.1], [12.7, 55.2], [11.5, 55.3],
      [11.0, 56.0], [10.0, 56.6], [8.8, 57.1], [7.2, 57.6], [5.9, 58.0],
      [4.9, 57.7],
    ],
  },
  {
    name: 'Mainland Europe',
    points: [
      [-8.0, 48.0], [31.5, 48.0], [31.5, 59.0], [29.0, 58.7], [26.0, 57.8],
      [24.3, 56.3], [22.0, 56.4], [20.6, 55.2], [18.2, 54.5], [15.3, 54.7],
      [13.8, 54.2], [12.3, 54.5], [10.1, 53.8], [7.4, 53.7], [4.8, 53.5],
      [1.8, 52.9], [-1.4, 53.5], [-4.0, 54.4], [-6.7, 55.0], [-8.0, 55.0],
      [-8.0, 48.0],
    ],
  },
  {
    name: 'Jutland',
    points: [[8.1, 54.8], [8.4, 56.0], [9.0, 57.4], [10.1, 57.6], [10.6, 56.3], [10.3, 55.2], [9.5, 54.6], [8.7, 54.5], [8.1, 54.8]],
  },
  {
    name: 'Zealand',
    points: [[11.2, 55.2], [11.7, 55.8], [12.4, 56.0], [12.8, 55.6], [12.5, 55.1], [11.8, 54.9], [11.2, 55.2]],
  },
  {
    name: 'Funen',
    points: [[9.7, 55.0], [10.5, 55.3], [10.7, 55.8], [10.0, 56.0], [9.5, 55.6], [9.7, 55.0]],
  },
  {
    name: 'Gotland',
    points: [[18.1, 56.9], [18.8, 57.6], [19.2, 57.9], [19.0, 57.1], [18.5, 56.8], [18.1, 56.9]],
  },
  {
    name: 'Oland',
    points: [[16.4, 56.2], [16.7, 57.2], [16.9, 57.4], [16.8, 56.3], [16.5, 56.0], [16.4, 56.2]],
  },
  {
    name: 'Bornholm',
    points: [[14.6, 55.0], [15.2, 55.2], [15.4, 55.0], [15.0, 54.8], [14.6, 55.0]],
  },
];

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
  const driveLinkTarget = ' target="_blank" rel="noopener"';
  if (confirmTexts.length > 0) {
    const confirmText = confirmTexts.join('\n');
    popupText += `<a${driveLinkClass} href="${destinationUrl}"${driveLinkTarget} onclick="return window.confirm('${confirmText}')">Drive here!</a>`;
  } else {
    popupText += `<a${driveLinkClass} href="${destinationUrl}"${driveLinkTarget}>Drive here!</a>`;
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

function parsePublicationCoordinate(value) {
  const coordinate = parseFloat(value);
  return Number.isFinite(coordinate) ? coordinate : 0;
}

function isValidPublicationCoordinate(lat, lon) {
  return Number.isFinite(lat) && Number.isFinite(lon)
    && lat >= -90 && lat <= 90
    && lon >= -180 && lon <= 180
    && lat !== 0 && lon !== 0;
}

export function getPublicationMapCoordinate(inscription, locationMode = 'current') {
  const foundLat = parsePublicationCoordinate(inscription?.latitude);
  const foundLon = parsePublicationCoordinate(inscription?.longitude);
  const presentLat = parsePublicationCoordinate(inscription?.present_latitude);
  const presentLon = parsePublicationCoordinate(inscription?.present_longitude);

  if (locationMode === 'original') {
    return isValidPublicationCoordinate(foundLat, foundLon)
      ? {lat: foundLat, lon: foundLon, source: 'original'}
      : null;
  }

  if (isValidPublicationCoordinate(presentLat, presentLon)) {
    return {lat: presentLat, lon: presentLon, source: 'current'};
  }
  if (isValidPublicationCoordinate(foundLat, foundLon)) {
    return {lat: foundLat, lon: foundLon, source: 'original'};
  }
  return null;
}

function normalizePublicationMapPoints(inscriptions, locationMode) {
  const points = [];
  let skippedCount = 0;

  (inscriptions || []).forEach((inscription) => {
    const coordinate = getPublicationMapCoordinate(inscription, locationMode);
    if (!coordinate) {
      skippedCount += 1;
      return;
    }
    points.push({
      id: inscription?.id,
      signature: String(inscription?.signature_text || inscription?.signature_header || inscription?.signature || '').trim(),
      ...coordinate,
    });
  });

  return {points, skippedCount};
}

function normalizePublicationMapGroup(group, groupIndex, locationMode, fallbackOptions = {}) {
  const normalized = normalizePublicationMapPoints(group.inscriptions || [], locationMode);
  const label = String(group.groupName || group.name || fallbackOptions.groupName || `Group ${groupIndex + 1}`).trim() || `Group ${groupIndex + 1}`;
  const groupOptions = {
    ...fallbackOptions,
    ...group,
    groupName: label,
  };

  return {
    index: groupIndex,
    name: label,
    options: groupOptions,
    points: normalized.points.map(point => ({
      ...point,
      groupIndex,
    })),
    skippedCount: normalized.skippedCount,
  };
}

function normalizePublicationMapGroups(groups, locationMode, fallbackOptions = {}) {
  return (groups || [])
    .map((group, index) => normalizePublicationMapGroup(group, index, locationMode, fallbackOptions))
    .filter(group => group.points.length > 0);
}

function getPublicationMapPointBounds(points) {
  return {
    minLat: Math.min(...points.map(point => point.lat)),
    maxLat: Math.max(...points.map(point => point.lat)),
    minLon: Math.min(...points.map(point => point.lon)),
    maxLon: Math.max(...points.map(point => point.lon)),
  };
}

function expandPublicationMapBounds(points) {
  let {minLat, maxLat, minLon, maxLon} = getPublicationMapPointBounds(points);

  const latCenter = (minLat + maxLat) / 2;
  const lonCenter = (minLon + maxLon) / 2;
  const latSpan = Math.max(maxLat - minLat, PUBLICATION_MAP_MIN_LAT_SPAN);
  const lonSpan = Math.max(maxLon - minLon, PUBLICATION_MAP_MIN_LON_SPAN);

  minLat = latCenter - latSpan / 2;
  maxLat = latCenter + latSpan / 2;
  minLon = lonCenter - lonSpan / 2;
  maxLon = lonCenter + lonSpan / 2;

  const paddedLatSpan = maxLat - minLat;
  const paddedLonSpan = maxLon - minLon;
  minLat = Math.max(-84, minLat - paddedLatSpan * 0.14);
  maxLat = Math.min(84, maxLat + paddedLatSpan * 0.14);
  minLon = Math.max(-180, minLon - paddedLonSpan * 0.14);
  maxLon = Math.min(180, maxLon + paddedLonSpan * 0.14);

  return {minLat, maxLat, minLon, maxLon};
}

function mercatorY(lat) {
  const clampedLat = Math.max(-84, Math.min(84, lat));
  return Math.log(Math.tan(Math.PI / 4 + (clampedLat * Math.PI / 180) / 2));
}

function mercatorToLat(y) {
  return (2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180 / Math.PI;
}

export function applyPublicationMapBoundsZoom(bounds, points = [], zoomLevel = 0) {
  const requestedZoom = parseInt(zoomLevel, 10);
  const clampedZoom = Math.max(-2, Math.min(2, Number.isFinite(requestedZoom) ? requestedZoom : 0));
  if (clampedZoom === 0) {
    return {...bounds};
  }

  const zoomScale = clampedZoom > 0
    ? Math.pow(0.72, clampedZoom)
    : Math.pow(1.45, Math.abs(clampedZoom));
  let minX = bounds.minLon * Math.PI / 180;
  let maxX = bounds.maxLon * Math.PI / 180;
  let minY = mercatorY(bounds.minLat);
  let maxY = mercatorY(bounds.maxLat);
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  const xSpan = Math.max(maxX - minX, 0.00001) * zoomScale;
  const ySpan = Math.max(maxY - minY, 0.00001) * zoomScale;

  minX = centerX - xSpan / 2;
  maxX = centerX + xSpan / 2;
  minY = centerY - ySpan / 2;
  maxY = centerY + ySpan / 2;

  if (Array.isArray(points) && points.length > 0) {
    const pointBounds = getPublicationMapPointBounds(points);
    const pointMinX = pointBounds.minLon * Math.PI / 180;
    const pointMaxX = pointBounds.maxLon * Math.PI / 180;
    const pointMinY = mercatorY(pointBounds.minLat);
    const pointMaxY = mercatorY(pointBounds.maxLat);
    const minPointXSpan = PUBLICATION_MAP_MIN_LON_SPAN * Math.PI / 180;
    const minPointYSpan = Math.max(
      mercatorY(pointBounds.minLat + PUBLICATION_MAP_MIN_LAT_SPAN / 2) - mercatorY(pointBounds.minLat - PUBLICATION_MAP_MIN_LAT_SPAN / 2),
      0.00001
    );
    const safeXPadding = Math.max(pointMaxX - pointMinX, minPointXSpan) * 0.06;
    const safeYPadding = Math.max(pointMaxY - pointMinY, minPointYSpan) * 0.06;

    minX = Math.min(minX, pointMinX - safeXPadding);
    maxX = Math.max(maxX, pointMaxX + safeXPadding);
    minY = Math.min(minY, pointMinY - safeYPadding);
    maxY = Math.max(maxY, pointMaxY + safeYPadding);
  }

  return {
    minLat: Math.max(-84, mercatorToLat(minY)),
    maxLat: Math.min(84, mercatorToLat(maxY)),
    minLon: Math.max(-180, minX * 180 / Math.PI),
    maxLon: Math.min(180, maxX * 180 / Math.PI),
  };
}

export function expandPublicationMapBoundsToAspect(bounds, width = PUBLICATION_MAP_WIDTH, height = PUBLICATION_MAP_HEIGHT, margin = PUBLICATION_MAP_MARGIN) {
  const drawableWidth = width - margin.left - margin.right;
  const drawableHeight = height - margin.top - margin.bottom;
  const targetRatio = drawableWidth / drawableHeight;
  let minX = bounds.minLon * Math.PI / 180;
  let maxX = bounds.maxLon * Math.PI / 180;
  let minY = mercatorY(bounds.minLat);
  let maxY = mercatorY(bounds.maxLat);
  const xSpan = Math.max(maxX - minX, 0.00001);
  const ySpan = Math.max(maxY - minY, 0.00001);
  const currentRatio = xSpan / ySpan;

  if (currentRatio < targetRatio) {
    const expandedXSpan = ySpan * targetRatio;
    const centerX = (minX + maxX) / 2;
    minX = centerX - expandedXSpan / 2;
    maxX = centerX + expandedXSpan / 2;
  } else if (currentRatio > targetRatio) {
    const expandedYSpan = xSpan / targetRatio;
    const centerY = (minY + maxY) / 2;
    minY = centerY - expandedYSpan / 2;
    maxY = centerY + expandedYSpan / 2;
  }

  return {
    minLat: Math.max(-84, mercatorToLat(minY)),
    maxLat: Math.min(84, mercatorToLat(maxY)),
    minLon: Math.max(-180, minX * 180 / Math.PI),
    maxLon: Math.min(180, maxX * 180 / Math.PI),
  };
}

function makePublicationMapProjection(bounds, width, height, margin) {
  const drawableWidth = width - margin.left - margin.right;
  const drawableHeight = height - margin.top - margin.bottom;
  const minX = bounds.minLon * Math.PI / 180;
  const maxX = bounds.maxLon * Math.PI / 180;
  const minY = mercatorY(bounds.minLat);
  const maxY = mercatorY(bounds.maxLat);
  const scale = Math.min(
    drawableWidth / Math.max(maxX - minX, 0.00001),
    drawableHeight / Math.max(maxY - minY, 0.00001)
  );
  const mapWidth = (maxX - minX) * scale;
  const mapHeight = (maxY - minY) * scale;
  const offsetX = margin.left + (drawableWidth - mapWidth) / 2;
  const offsetY = margin.top + (drawableHeight - mapHeight) / 2;

  return {
    mapRect: {x: offsetX, y: offsetY, width: mapWidth, height: mapHeight},
    project(lat, lon) {
      return {
        x: offsetX + ((lon * Math.PI / 180) - minX) * scale,
        y: offsetY + (maxY - mercatorY(lat)) * scale,
      };
    },
  };
}

function lonToOsmPixelX(lon, zoom) {
  const worldSize = PUBLICATION_MAP_TILE_SIZE * (2 ** zoom);
  return ((lon + 180) / 360) * worldSize;
}

function latToOsmPixelY(lat, zoom) {
  const worldSize = PUBLICATION_MAP_TILE_SIZE * (2 ** zoom);
  const clampedLat = Math.max(-85.05112878, Math.min(85.05112878, lat));
  const latRad = clampedLat * Math.PI / 180;
  return (0.5 - Math.log((1 + Math.sin(latRad)) / (1 - Math.sin(latRad))) / (4 * Math.PI)) * worldSize;
}

function makePublicationMapOsmProjection(bounds, width, height, margin, zoom) {
  const drawableWidth = width - margin.left - margin.right;
  const drawableHeight = height - margin.top - margin.bottom;
  const minPixelX = lonToOsmPixelX(bounds.minLon, zoom);
  const maxPixelX = lonToOsmPixelX(bounds.maxLon, zoom);
  const minPixelY = latToOsmPixelY(bounds.maxLat, zoom);
  const maxPixelY = latToOsmPixelY(bounds.minLat, zoom);
  const pixelWidth = Math.max(maxPixelX - minPixelX, 0.00001);
  const pixelHeight = Math.max(maxPixelY - minPixelY, 0.00001);
  const scale = Math.min(drawableWidth / pixelWidth, drawableHeight / pixelHeight);
  const mapWidth = pixelWidth * scale;
  const mapHeight = pixelHeight * scale;
  const offsetX = margin.left + (drawableWidth - mapWidth) / 2;
  const offsetY = margin.top + (drawableHeight - mapHeight) / 2;

  return {
    zoom,
    minPixelX,
    maxPixelX,
    minPixelY,
    maxPixelY,
    scale,
    mapRect: {x: offsetX, y: offsetY, width: mapWidth, height: mapHeight},
    project(lat, lon) {
      return {
        x: offsetX + (lonToOsmPixelX(lon, zoom) - minPixelX) * scale,
        y: offsetY + (latToOsmPixelY(lat, zoom) - minPixelY) * scale,
      };
    },
    pixelToSvg(pixelX, pixelY) {
      return {
        x: offsetX + (pixelX - minPixelX) * scale,
        y: offsetY + (pixelY - minPixelY) * scale,
      };
    },
  };
}

function getPublicationMapOsmTileRange(projection) {
  const maxTileIndex = (2 ** projection.zoom) - 1;
  return {
    minX: Math.max(0, Math.floor(projection.minPixelX / PUBLICATION_MAP_TILE_SIZE)),
    maxX: Math.min(maxTileIndex, Math.floor(projection.maxPixelX / PUBLICATION_MAP_TILE_SIZE)),
    minY: Math.max(0, Math.floor(projection.minPixelY / PUBLICATION_MAP_TILE_SIZE)),
    maxY: Math.min(maxTileIndex, Math.floor(projection.maxPixelY / PUBLICATION_MAP_TILE_SIZE)),
  };
}

function countPublicationMapOsmTiles(range) {
  return Math.max(0, range.maxX - range.minX + 1) * Math.max(0, range.maxY - range.minY + 1);
}

function getPublicationMapTileProvider(providerId = 'osm') {
  return PUBLICATION_MAP_TILE_PROVIDERS[providerId] || PUBLICATION_MAP_TILE_PROVIDERS.osm;
}

export function choosePublicationMapOsmZoom(bounds, width = PUBLICATION_MAP_WIDTH, height = PUBLICATION_MAP_HEIGHT) {
  let selectedZoom = PUBLICATION_MAP_OSM_MIN_ZOOM;
  const framedBounds = expandPublicationMapBoundsToAspect(bounds, width, height, PUBLICATION_MAP_MARGIN);

  for (let zoom = PUBLICATION_MAP_OSM_MIN_ZOOM; zoom <= PUBLICATION_MAP_OSM_MAX_ZOOM; zoom += 1) {
    const projection = makePublicationMapOsmProjection(framedBounds, width, height, PUBLICATION_MAP_MARGIN, zoom);
    const tileCount = countPublicationMapOsmTiles(getPublicationMapOsmTileRange(projection));
    if (tileCount > PUBLICATION_MAP_OSM_MAX_TILES) {
      break;
    }
    selectedZoom = zoom;
  }

  return selectedZoom;
}

export function getPublicationMapOsmTileLayout(bounds, width = PUBLICATION_MAP_WIDTH, height = PUBLICATION_MAP_HEIGHT, providerId = 'osm') {
  const provider = getPublicationMapTileProvider(providerId);
  const framedBounds = expandPublicationMapBoundsToAspect(bounds, width, height, PUBLICATION_MAP_MARGIN);
  const zoom = choosePublicationMapOsmZoom(framedBounds, width, height);
  const projection = makePublicationMapOsmProjection(framedBounds, width, height, PUBLICATION_MAP_MARGIN, zoom);
  const range = getPublicationMapOsmTileRange(projection);
  const tiles = [];

  for (let y = range.minY; y <= range.maxY; y += 1) {
    for (let x = range.minX; x <= range.maxX; x += 1) {
      const topLeft = projection.pixelToSvg(x * PUBLICATION_MAP_TILE_SIZE, y * PUBLICATION_MAP_TILE_SIZE);
      const tileSize = PUBLICATION_MAP_TILE_SIZE * projection.scale;
      tiles.push({
        x,
        y,
        z: zoom,
        url: provider.tileUrl
          .replace('{z}', String(zoom))
          .replace('{x}', String(x))
          .replace('{y}', String(y)),
        svgX: topLeft.x,
        svgY: topLeft.y,
        svgSize: tileSize,
      });
    }
  }

  return {projection, tiles, bounds: framedBounds, provider};
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error('Could not read map tile image.'));
    reader.readAsDataURL(blob);
  });
}

async function fetchPublicationMapTileDataUrl(url, fetchTile = null) {
  const fetchFunction = fetchTile || (typeof fetch === 'function' ? fetch.bind(globalThis) : null);
  if (!fetchFunction) {
    throw new Error('This browser cannot fetch map tiles for export.');
  }

  const controller = typeof AbortController === 'function' ? new AbortController() : null;
  const requestOptions = controller ? {cache: 'default', signal: controller.signal} : {cache: 'default'};
  const timeoutId = controller
    ? setTimeout(() => controller.abort(), PUBLICATION_MAP_TILE_FETCH_TIMEOUT_MS)
    : null;

  try {
    const response = await fetchFunction(url, requestOptions);
    if (!response || !response.ok) {
      throw new Error(`Could not fetch map tile: ${url}`);
    }
    return blobToDataUrl(await response.blob());
  } catch (error) {
    if (error && error.name === 'AbortError') {
      throw new Error(`Timed out while fetching map tile: ${url}`);
    }
    throw error;
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
}

async function mapPublicationMapTilesWithLimit(tiles, mapper, concurrency = PUBLICATION_MAP_TILE_FETCH_CONCURRENCY) {
  const results = new Array(tiles.length);
  let nextIndex = 0;
  const workerCount = Math.max(1, Math.min(concurrency, tiles.length));
  const workers = Array.from({length: workerCount}, async () => {
    while (nextIndex < tiles.length) {
      const tileIndex = nextIndex;
      nextIndex += 1;
      results[tileIndex] = await mapper(tiles[tileIndex], tileIndex);
    }
  });

  await Promise.all(workers);
  return results;
}

function escapeSvgText(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function getPublicationMapGridStep(span) {
  if (span <= 4) return 1;
  if (span <= 9) return 2;
  if (span <= 20) return 5;
  return 10;
}

function buildPublicationMapGrid(bounds, projection) {
  const lines = [];
  const latStep = getPublicationMapGridStep(bounds.maxLat - bounds.minLat);
  const lonStep = getPublicationMapGridStep(bounds.maxLon - bounds.minLon);

  for (let lat = Math.ceil(bounds.minLat / latStep) * latStep; lat < bounds.maxLat; lat += latStep) {
    const start = projection.project(lat, bounds.minLon);
    const end = projection.project(lat, bounds.maxLon);
    lines.push(`<line class="graticule" x1="${start.x.toFixed(1)}" y1="${start.y.toFixed(1)}" x2="${end.x.toFixed(1)}" y2="${end.y.toFixed(1)}"/>`);
  }

  for (let lon = Math.ceil(bounds.minLon / lonStep) * lonStep; lon < bounds.maxLon; lon += lonStep) {
    const start = projection.project(bounds.minLat, lon);
    const end = projection.project(bounds.maxLat, lon);
    lines.push(`<line class="graticule" x1="${start.x.toFixed(1)}" y1="${start.y.toFixed(1)}" x2="${end.x.toFixed(1)}" y2="${end.y.toFixed(1)}"/>`);
  }

  return lines.join('\n');
}

function buildPublicationMapLand(projection) {
  return PUBLICATION_MAP_LAND_POLYGONS.map((polygon) => {
    const path = polygon.points
      .map(([lon, lat], index) => {
        const point = projection.project(lat, lon);
        return `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`;
      })
      .join(' ');
    return `<path class="land" d="${path} Z"><title>${escapeSvgText(polygon.name)}</title></path>`;
  }).join('\n');
}

function getPublicationMapSymbolColor(options) {
  if (/^#[0-9a-fA-F]{6}$/.test(String(options.symbolColour || ''))) {
    return options.symbolColour;
  }
  return '#111111';
}

function getPublicationMapSymbolSize(options) {
  const requestedSize = parseFloat(options.symbolSize);
  if (!Number.isFinite(requestedSize)) {
    return 6;
  }
  return Math.max(1, Math.min(6, requestedSize));
}

function buildPublicationMapSymbol(point, projection, options) {
  const projected = projection.project(point.lat, point.lon);
  const size = getPublicationMapSymbolSize(options);
  const color = getPublicationMapSymbolColor(options);
  const title = escapeSvgText(point.signature || `Inscription ${point.id || ''}`.trim());
  const x = projected.x.toFixed(1);
  const y = projected.y.toFixed(1);

  if (options.symbol === 'triangle') {
    const path = [
      `${x},${(projected.y - size).toFixed(1)}`,
      `${(projected.x + size).toFixed(1)},${(projected.y + size * 0.8).toFixed(1)}`,
      `${(projected.x - size).toFixed(1)},${(projected.y + size * 0.8).toFixed(1)}`,
    ].join(' ');
    return `<polygon class="inscription-symbol" points="${path}" fill="${color}"><title>${title}</title></polygon>`;
  }
  if (options.symbol === 'square') {
    return `<rect class="inscription-symbol" x="${(projected.x - size).toFixed(1)}" y="${(projected.y - size).toFixed(1)}" width="${(size * 2).toFixed(1)}" height="${(size * 2).toFixed(1)}" fill="${color}"><title>${title}</title></rect>`;
  }
  return `<circle class="inscription-symbol" cx="${x}" cy="${y}" r="${size.toFixed(1)}" fill="${color}"><title>${title}</title></circle>`;
}

function truncatePublicationMapLabel(value, maxLength = 28) {
  const text = String(value || '').trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, Math.max(0, maxLength - 3))}...`;
}

function wrapPublicationMapText(value, maxCharacters) {
  const words = String(value || '').trim().split(/\s+/).filter(Boolean);
  const lines = [];
  let currentLine = '';

  words.forEach((word) => {
    const candidateLine = currentLine ? `${currentLine} ${word}` : word;
    if (candidateLine.length > maxCharacters && currentLine) {
      lines.push(currentLine);
      currentLine = word;
      return;
    }
    currentLine = candidateLine;
  });

  if (currentLine) {
    lines.push(currentLine);
  }
  return lines.length > 0 ? lines : [''];
}

function buildPublicationMapCaption(caption, width, height) {
  const maxCharacters = Math.max(70, Math.floor((width - PUBLICATION_MAP_MARGIN.left - PUBLICATION_MAP_MARGIN.right) / 7));
  const lineHeight = 14;
  const lines = wrapPublicationMapText(caption, maxCharacters);
  const startY = height - 20 - (lines.length - 1) * lineHeight;
  const tspans = lines.map((line, index) => (
    `<tspan x="${PUBLICATION_MAP_MARGIN.left}" y="${startY + index * lineHeight}">${escapeSvgText(line)}</tspan>`
  )).join('');

  return `<text class="caption">${tspans}</text>`;
}

function buildPublicationMapLegend(options, groups, projection) {
  const rect = projection.mapRect;
  const legendWidth = 282;
  const rowHeight = 23;
  const legendHeight = 48 + groups.length * rowHeight;
  const legendX = rect.x + rect.width - legendWidth - 18;
  const legendY = rect.y + 18;
  const legendTitle = escapeSvgText(truncatePublicationMapLabel(options.groupName || 'Search results', 30));
  const rows = groups.map((group, index) => {
    const rowY = legendY + 48 + index * rowHeight;
    const groupName = escapeSvgText(truncatePublicationMapLabel(group.name));
    const samplePoint = {lat: 0, lon: 0, signature: group.name};
    const sampleProjection = {
      project: () => ({x: legendX + 20, y: rowY - 5}),
    };
    const sampleSymbol = buildPublicationMapSymbol(samplePoint, sampleProjection, {
      ...options,
      ...group.options,
      symbolSize: Math.min(getPublicationMapSymbolSize(group.options), 5.5),
    });
    return `${sampleSymbol}
    <text x="${(legendX + 40).toFixed(1)}" y="${rowY.toFixed(1)}">${groupName}</text>
    <text class="legend-meta" x="${(legendX + legendWidth - 72).toFixed(1)}" y="${rowY.toFixed(1)}">${group.points.length}</text>`;
  }).join('\n');

  return `<g class="legend">
    <rect class="legend-frame" x="${legendX.toFixed(1)}" y="${legendY.toFixed(1)}" width="${legendWidth}" height="${legendHeight}" rx="3"/>
    <text class="legend-title" x="${(legendX + 14).toFixed(1)}" y="${(legendY + 24).toFixed(1)}">${legendTitle}</text>
    ${rows}
  </g>`;
}

function makePublicationMapContext(inscriptions, options = {}) {
  const locationMode = options.locationMode === 'original' ? 'original' : 'current';
  const groups = Array.isArray(options.groups) && options.groups.length > 0
    ? normalizePublicationMapGroups(options.groups, locationMode, options)
    : normalizePublicationMapGroups([{
      groupName: options.groupName || 'Search results',
      inscriptions,
      symbol: options.symbol,
      symbolSize: options.symbolSize,
      symbolColour: options.symbolColour,
    }], locationMode, options);
  const points = groups.flatMap(group => group.points);
  const skippedCount = groups.reduce((total, group) => total + group.skippedCount, 0);

  if (points.length === 0) {
    throw new Error('No inscriptions with usable coordinates are available for map export.');
  }
  return {
    groups,
    points,
    skippedCount,
    locationMode,
    bounds: expandPublicationMapBounds(points),
  };
}

function buildPublicationMapSvgDocument({
  width,
  height,
  points,
  groups,
  skippedCount,
  bounds,
  projection,
  options,
  baseMapMarkup,
  caption,
  attribution = '',
}) {
  const rect = projection.mapRect;
  const title = escapeSvgText(options.title || 'Rundata-net publication map');
  const groupCountText = groups.length > 1 ? ` in ${groups.length} groups` : '';
  const subtitle = escapeSvgText(`${points.length} inscription${points.length === 1 ? '' : 's'}${groupCountText}; ${options.locationMode === 'original' ? 'original locations' : 'current locations where available'}`);
  const symbols = groups
    .flatMap(group => group.points.map(point => buildPublicationMapSymbol(point, projection, {
      ...options,
      ...group.options,
    })))
    .join('\n');

  return {
    svg: `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="map-title map-description">
  <title id="map-title">${title}</title>
  <desc id="map-description">${subtitle}</desc>
  <defs>
    <clipPath id="publication-map-clip"><rect x="${rect.x.toFixed(1)}" y="${rect.y.toFixed(1)}" width="${rect.width.toFixed(1)}" height="${rect.height.toFixed(1)}"/></clipPath>
    <style>
      .page { fill: #ffffff; }
      .sea { fill: #f4f8fb; stroke: #313131; stroke-width: 1.2; }
      .graticule { stroke: #d7dde2; stroke-width: 0.8; }
      .land { fill: #f7f3e8; stroke: #707070; stroke-width: 1.1; stroke-linejoin: round; }
      .inscription-symbol { stroke: none; opacity: 0.92; }
      .title { fill: #111111; font-family: Arial, Helvetica, sans-serif; font-size: 26px; font-weight: 700; }
      .subtitle { fill: #4b4b4b; font-family: Arial, Helvetica, sans-serif; font-size: 15px; }
      .map-border { fill: none; stroke: #9a9a9a; stroke-width: 1; }
      .legend .legend-frame { fill: #ffffff; fill-opacity: 0.92; stroke: #333333; stroke-width: 0.8; }
      .legend text { fill: #111111; font-family: Arial, Helvetica, sans-serif; font-size: 14px; }
      .legend .legend-title { fill: #333333; font-size: 18px; font-weight: 700; }
      .legend .legend-meta { fill: #555555; font-size: 12px; }
      .caption { fill: #555555; font-family: Arial, Helvetica, sans-serif; font-size: 11px; }
      .attribution { fill: #555555; font-family: Arial, Helvetica, sans-serif; font-size: 10px; }
    </style>
  </defs>
  <rect class="page" width="${width}" height="${height}"/>
  <text class="title" x="${PUBLICATION_MAP_MARGIN.left}" y="42">${title}</text>
  <text class="subtitle" x="${PUBLICATION_MAP_MARGIN.left}" y="66">${subtitle}</text>
  ${baseMapMarkup}
  <rect class="map-border" x="${rect.x.toFixed(1)}" y="${rect.y.toFixed(1)}" width="${rect.width.toFixed(1)}" height="${rect.height.toFixed(1)}"/>
  <g clip-path="url(#publication-map-clip)">
    <g class="inscriptions">
      ${symbols}
    </g>
  </g>
  ${buildPublicationMapLegend(options, groups, projection)}
  ${attribution}
  ${buildPublicationMapCaption(caption, width, height)}
</svg>`,
    pointCount: points.length,
    skippedCount,
    bounds,
    width,
    height,
  };
}

function buildSimplePublicationMapBaseLayer(bounds, projection) {
  const rect = projection.mapRect;
  return `<rect class="sea" x="${rect.x.toFixed(1)}" y="${rect.y.toFixed(1)}" width="${rect.width.toFixed(1)}" height="${rect.height.toFixed(1)}"/>
  <g clip-path="url(#publication-map-clip)">
    ${buildPublicationMapGrid(bounds, projection)}
    ${buildPublicationMapLand(projection)}
  </g>`;
}

export function buildPublicationMapSvg(inscriptions, options = {}) {
  const width = options.width || PUBLICATION_MAP_WIDTH;
  const height = options.height || PUBLICATION_MAP_HEIGHT;
  const context = makePublicationMapContext(inscriptions, options);
  const zoomedBounds = applyPublicationMapBoundsZoom(context.bounds, context.points, options.zoom);
  const bounds = expandPublicationMapBoundsToAspect(zoomedBounds, width, height, PUBLICATION_MAP_MARGIN);
  const projection = makePublicationMapProjection(bounds, width, height, PUBLICATION_MAP_MARGIN);

  return buildPublicationMapSvgDocument({
    width,
    height,
    ...context,
    bounds,
    projection,
    options: {...options, locationMode: context.locationMode},
    baseMapMarkup: buildSimplePublicationMapBaseLayer(bounds, projection),
    caption: 'Simplified vector base map. Coordinates exported from Rundata-net. To publish or present this map, specify its source: https://rundata.info.',
  });
}

async function buildOsmPublicationMapBaseLayer(bounds, width, height, fetchTile = null, providerId = 'osm') {
  const {projection, tiles, bounds: framedBounds, provider} = getPublicationMapOsmTileLayout(bounds, width, height, providerId);
  const rect = projection.mapRect;
  const embeddedTiles = await mapPublicationMapTilesWithLimit(tiles, async (tile) => ({
    ...tile,
    dataUrl: await fetchPublicationMapTileDataUrl(tile.url, fetchTile),
  }));

  const tileMarkup = embeddedTiles.map((tile) => (
    `<image href="${tile.dataUrl}" xlink:href="${tile.dataUrl}" x="${tile.svgX.toFixed(1)}" y="${tile.svgY.toFixed(1)}" width="${tile.svgSize.toFixed(1)}" height="${tile.svgSize.toFixed(1)}" preserveAspectRatio="none"/>`
  )).join('\n');

  return {
    projection,
    bounds: framedBounds,
    provider,
    baseMapMarkup: `<rect class="sea" x="${rect.x.toFixed(1)}" y="${rect.y.toFixed(1)}" width="${rect.width.toFixed(1)}" height="${rect.height.toFixed(1)}"/>
  <g clip-path="url(#publication-map-clip)">
    ${tileMarkup}
  </g>`,
    attribution: `<text class="attribution" x="${(rect.x + 8).toFixed(1)}" y="${(rect.y + rect.height - 8).toFixed(1)}">${escapeSvgText(provider.attribution)}</text>`,
    tiles: embeddedTiles,
    tileCount: tiles.length,
    zoom: projection.zoom,
  };
}

function canvasToPublicationMapBlob(canvas) {
  return new Promise((resolve, reject) => {
    if (typeof canvas.toBlob === 'function') {
      canvas.toBlob((blob) => {
        if (blob) {
          resolve(blob);
        } else {
          reject(new Error('Could not create PNG map file.'));
        }
      }, 'image/png');
      return;
    }

    fetch(canvas.toDataURL('image/png'))
      .then(response => response.blob())
      .then(resolve)
      .catch(reject);
  });
}

function loadPublicationMapCanvasImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('Could not prepare map tile for PNG export.'));
    image.src = src;
  });
}

function drawPublicationMapCanvasSymbolAt(ctx, x, y, options) {
  const size = getPublicationMapSymbolSize(options);
  const color = getPublicationMapSymbolColor(options);

  ctx.save();
  ctx.globalAlpha = 0.92;
  ctx.fillStyle = color;

  if (options.symbol === 'triangle') {
    ctx.beginPath();
    ctx.moveTo(x, y - size);
    ctx.lineTo(x + size, y + size * 0.8);
    ctx.lineTo(x - size, y + size * 0.8);
    ctx.closePath();
    ctx.fill();
  } else if (options.symbol === 'square') {
    ctx.fillRect(x - size, y - size, size * 2, size * 2);
  } else {
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

function drawPublicationMapCanvasSymbol(ctx, point, projection, options) {
  const projected = projection.project(point.lat, point.lon);
  drawPublicationMapCanvasSymbolAt(ctx, projected.x, projected.y, options);
}

function roundedPublicationMapRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
}

function drawPublicationMapCanvasLegend(ctx, options, groups, projection) {
  const rect = projection.mapRect;
  const legendWidth = 282;
  const rowHeight = 23;
  const legendHeight = 48 + groups.length * rowHeight;
  const legendX = rect.x + rect.width - legendWidth - 18;
  const legendY = rect.y + 18;

  ctx.save();
  ctx.beginPath();
  roundedPublicationMapRect(ctx, legendX, legendY, legendWidth, legendHeight, 3);
  ctx.fillStyle = 'rgba(255, 255, 255, 0.92)';
  ctx.strokeStyle = '#333333';
  ctx.lineWidth = 0.8;
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#333333';
  ctx.font = '700 18px Arial, Helvetica, sans-serif';
  ctx.fillText(truncatePublicationMapLabel(options.groupName || 'Search results', 30), legendX + 14, legendY + 24);

  groups.forEach((group, index) => {
    const rowY = legendY + 48 + index * rowHeight;
    drawPublicationMapCanvasSymbolAt(ctx, legendX + 20, rowY - 5, {
      ...options,
      ...group.options,
      symbolSize: Math.min(getPublicationMapSymbolSize(group.options), 5.5),
    });
    ctx.fillStyle = '#111111';
    ctx.font = '14px Arial, Helvetica, sans-serif';
    ctx.fillText(truncatePublicationMapLabel(group.name), legendX + 40, rowY);
    ctx.fillStyle = '#555555';
    ctx.font = '12px Arial, Helvetica, sans-serif';
    ctx.fillText(String(group.points.length), legendX + legendWidth - 72, rowY);
  });
  ctx.restore();
}

function drawPublicationMapCanvasCaption(ctx, caption, width, height) {
  const maxCharacters = Math.max(70, Math.floor((width - PUBLICATION_MAP_MARGIN.left - PUBLICATION_MAP_MARGIN.right) / 7));
  const lineHeight = 14;
  const lines = wrapPublicationMapText(caption, maxCharacters);
  const startY = height - 20 - (lines.length - 1) * lineHeight;

  ctx.save();
  ctx.fillStyle = '#555555';
  ctx.font = '11px Arial, Helvetica, sans-serif';
  lines.forEach((line, index) => {
    ctx.fillText(line, PUBLICATION_MAP_MARGIN.left, startY + index * lineHeight);
  });
  ctx.restore();
}

export async function buildPublicationMapPngBlob(inscriptions, options = {}) {
  if (typeof document === 'undefined') {
    throw new Error('PNG map export requires a browser canvas.');
  }

  const width = options.width || PUBLICATION_MAP_WIDTH;
  const height = options.height || PUBLICATION_MAP_HEIGHT;
  const scale = Math.max(1, Math.min(3, parseFloat(options.pngScale) || 2));
  const context = makePublicationMapContext(inscriptions, options);
  const providerId = options.background === 'carto-positron' ? 'carto-positron' : 'osm';
  const zoomedBounds = applyPublicationMapBoundsZoom(context.bounds, context.points, options.zoom);
  const osmLayer = await buildOsmPublicationMapBaseLayer(zoomedBounds, width, height, options.fetchTile || null, providerId);
  const rect = osmLayer.projection.mapRect;
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('Could not prepare PNG map canvas.');
  }
  ctx.scale(scale, scale);

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = '#f4f8fb';
  ctx.fillRect(rect.x, rect.y, rect.width, rect.height);

  ctx.save();
  ctx.beginPath();
  ctx.rect(rect.x, rect.y, rect.width, rect.height);
  ctx.clip();
  const tileImages = await Promise.all(osmLayer.tiles.map(tile => loadPublicationMapCanvasImage(tile.dataUrl)));
  osmLayer.tiles.forEach((tile, index) => {
    ctx.drawImage(tileImages[index], tile.svgX, tile.svgY, tile.svgSize, tile.svgSize);
  });
  context.groups.forEach((group) => {
    group.points.forEach(point => drawPublicationMapCanvasSymbol(ctx, point, osmLayer.projection, {
      ...options,
      ...group.options,
    }));
  });
  ctx.restore();

  ctx.strokeStyle = '#9a9a9a';
  ctx.lineWidth = 1;
  ctx.strokeRect(rect.x, rect.y, rect.width, rect.height);

  const title = options.title || 'Rundata-net publication map';
  const groupCountText = context.groups.length > 1 ? ` in ${context.groups.length} groups` : '';
  const subtitle = `${context.points.length} inscription${context.points.length === 1 ? '' : 's'}${groupCountText}; ${context.locationMode === 'original' ? 'original locations' : 'current locations where available'}`;
  ctx.fillStyle = '#111111';
  ctx.font = '700 26px Arial, Helvetica, sans-serif';
  ctx.fillText(title, PUBLICATION_MAP_MARGIN.left, 42);
  ctx.fillStyle = '#4b4b4b';
  ctx.font = '15px Arial, Helvetica, sans-serif';
  ctx.fillText(subtitle, PUBLICATION_MAP_MARGIN.left, 66);

  drawPublicationMapCanvasLegend(ctx, {...options, locationMode: context.locationMode}, context.groups, osmLayer.projection);

  ctx.fillStyle = '#555555';
  ctx.font = '10px Arial, Helvetica, sans-serif';
  ctx.fillText(osmLayer.provider.attribution, rect.x + 8, rect.y + rect.height - 8);
  drawPublicationMapCanvasCaption(ctx, osmLayer.provider.caption, width, height);

  return {
    blob: await canvasToPublicationMapBlob(canvas),
    pointCount: context.points.length,
    skippedCount: context.skippedCount,
    width,
    height,
    baseMap: providerId,
    tileCount: osmLayer.tileCount,
    zoom: osmLayer.zoom,
  };
}

export async function buildPublicationMapSvgWithOsm(inscriptions, options = {}) {
  const width = options.width || PUBLICATION_MAP_WIDTH;
  const height = options.height || PUBLICATION_MAP_HEIGHT;
  const context = makePublicationMapContext(inscriptions, options);
  const providerId = options.background === 'carto-positron' ? 'carto-positron' : 'osm';
  const zoomedBounds = applyPublicationMapBoundsZoom(context.bounds, context.points, options.zoom);
  const osmLayer = await buildOsmPublicationMapBaseLayer(zoomedBounds, width, height, options.fetchTile || null, providerId);

  return {
    ...buildPublicationMapSvgDocument({
      width,
      height,
      ...context,
      bounds: osmLayer.bounds,
      projection: osmLayer.projection,
      options: {...options, locationMode: context.locationMode},
      baseMapMarkup: osmLayer.baseMapMarkup,
      attribution: osmLayer.attribution,
      caption: osmLayer.provider.caption,
    }),
    baseMap: providerId,
    tileCount: osmLayer.tileCount,
    zoom: osmLayer.zoom,
  };
}
