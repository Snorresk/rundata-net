import { test } from 'uvu';
import * as assert from 'uvu/assert';
import {
  getMarkerClusterOptions,
  getSpiderfiedTooltipDirection,
  handleMobileClusterClick,
  inscriptions2markers,
  openMobileInscriptionInfo,
  positionSpiderfiedTooltips,
  resetSpiderfiedTooltips,
  shouldSpiderfyNearbyPair,
  shouldSpiderfySharedCoordinates,
} from '../../runes/js/index_map.js';

const mockLeaflet = {
  marker: (latlng, options) => {
      const tooltipElement = {
        dataset: {},
        attributes: {},
        listeners: {},
        setAttribute: (name, value) => {
          tooltipElement.attributes[name] = value;
        },
        addEventListener: (eventName, handler) => {
          tooltipElement.listeners[eventName] = handler;
        },
      };
      const tooltipObj = {
        getElement: () => tooltipElement,
      };
      const markerObj = {
        _latlng: latlng,
        options: options,
        getLatLng: () => {
          return {
            lat: latlng[0],
            lng: latlng[1]
          }
        },
        bindPopup: (popupText, popupOptions) => {
          markerObj.popupText = popupText;
          markerObj.popupOptions = popupOptions;
          return markerObj;
        },
        bindTooltip: (tooltipText, tooltipOptions) => {
          markerObj.tooltipText = tooltipText;
          markerObj.tooltipOptions = tooltipOptions;
          return markerObj;
        },
        openTooltip: () => markerObj,
        getTooltip: () => tooltipObj,
        on: (eventName, handler) => {
          markerObj.events[eventName] = handler;
          return markerObj;
        },
        openPopup: () => {
          markerObj.openPopupCalled = true;
          return markerObj;
        },
        events: {},
        tooltipElement,
      };
      return markerObj;
  }
};

function makeClusterMock(markerCoordinates) {
  const childMarkers = markerCoordinates.map(([lat, lng]) => ({
    getLatLng: () => ({lat, lng}),
  }));
  const cluster = {
    getChildCount: () => childMarkers.length,
    getAllChildMarkers: () => childMarkers,
    spiderfy: () => {
      cluster.spiderfyCalled = true;
    },
    zoomToBounds: () => {
      cluster.zoomToBoundsCalled = true;
    },
  };
  return cluster;
}

function makeMapMock(distanceMeters, zoom = 10, maxZoom = 19) {
  return {
    distance: () => distanceMeters,
    getZoom: () => zoom,
    getMaxZoom: () => maxZoom,
  };
}

function makeSpiderfyMarker(lat, lng) {
  const tooltip = {
    options: {direction: 'auto'},
    update: () => {
      tooltip.updateCount = (tooltip.updateCount || 0) + 1;
    },
  };
  return {
    getLatLng: () => ({lat, lng}),
    getTooltip: () => tooltip,
    tooltip,
  };
}

test('shouldSpiderfyNearbyPair() accepts only nearby two-marker clusters', () => {
  const nearbyPair = makeClusterMock([[58.416765, 15.522882], [58.416846, 15.522864]]);
  const threeMarkers = makeClusterMock([[1, 1], [1, 1.0001], [1, 1.0002]]);

  assert.is(shouldSpiderfyNearbyPair(nearbyPair, makeMapMock(9)), true);
  assert.is(shouldSpiderfyNearbyPair(nearbyPair, makeMapMock(101)), false);
  assert.is(shouldSpiderfyNearbyPair(threeMarkers, makeMapMock(9)), false);
});

test('handleMobileClusterClick() immediately spiderfies a nearby pair', () => {
  const cluster = makeClusterMock([[58.416765, 15.522882], [58.416846, 15.522864]]);

  handleMobileClusterClick({layer: cluster}, makeMapMock(9));

  assert.is(cluster.spiderfyCalled, true);
  assert.is(cluster.zoomToBoundsCalled, undefined);
});

test('shouldSpiderfySharedCoordinates() accepts small clusters at one point', () => {
  const exactPair = makeClusterMock([[58.366819, 15.371625], [58.366819, 15.371625]]);
  const exactTriple = makeClusterMock([[1, 1], [1, 1], [1, 1]]);
  const differentCoordinates = makeClusterMock([[1, 1], [1, 1.000001], [1, 1]]);
  const largeExactCluster = makeClusterMock(Array.from({length: 11}, () => [1, 1]));

  assert.is(shouldSpiderfySharedCoordinates(exactPair), true);
  assert.is(shouldSpiderfySharedCoordinates(exactTriple), true);
  assert.is(shouldSpiderfySharedCoordinates(differentCoordinates), false);
  assert.is(shouldSpiderfySharedCoordinates(largeExactCluster), false);
});

test('handleMobileClusterClick() immediately spiderfies shared coordinates', () => {
  const cluster = makeClusterMock([[1, 1], [1, 1], [1, 1]]);

  handleMobileClusterClick({layer: cluster}, makeMapMock(0));

  assert.is(cluster.spiderfyCalled, true);
  assert.is(cluster.zoomToBoundsCalled, undefined);
});

test('handleMobileClusterClick() keeps normal zoom for other clusters', () => {
  const distantPair = makeClusterMock([[58, 15], [59, 16]]);

  handleMobileClusterClick({layer: distantPair}, makeMapMock(500));

  assert.is(distantPair.spiderfyCalled, undefined);
  assert.is(distantPair.zoomToBoundsCalled, true);
});

test('getMarkerClusterOptions() changes cluster clicks only on mobile', () => {
  const desktopOptions = getMarkerClusterOptions(false);
  const mobileOptions = getMarkerClusterOptions(true);

  assert.is(desktopOptions.zoomToBoundsOnClick, undefined);
  assert.is(desktopOptions.spiderfyOnMaxZoom, undefined);
  assert.is(mobileOptions.zoomToBoundsOnClick, false);
  assert.is(mobileOptions.spiderfyOnMaxZoom, false);
  assert.is(mobileOptions.maxClusterRadius, desktopOptions.maxClusterRadius);
});

test('getSpiderfiedTooltipDirection() points labels away from cluster center', () => {
  const cluster = {getLatLng: () => ({lat: 0, lng: 0})};
  const map = {
    latLngToLayerPoint: ({lat, lng}) => ({x: lng, y: -lat}),
  };

  assert.is(getSpiderfiedTooltipDirection(makeSpiderfyMarker(0, 1), cluster, map), 'right');
  assert.is(getSpiderfiedTooltipDirection(makeSpiderfyMarker(0, -1), cluster, map), 'left');
  assert.is(getSpiderfiedTooltipDirection(makeSpiderfyMarker(1, 0), cluster, map), 'top');
  assert.is(getSpiderfiedTooltipDirection(makeSpiderfyMarker(-1, 0), cluster, map), 'bottom');
});

test('spiderfied tooltip directions are applied and then restored', () => {
  const markers = [
    makeSpiderfyMarker(0, 1),
    makeSpiderfyMarker(0, -1),
  ];
  const cluster = {getLatLng: () => ({lat: 0, lng: 0})};
  const map = {
    latLngToLayerPoint: ({lat, lng}) => ({x: lng, y: -lat}),
  };
  const event = {cluster, markers};

  positionSpiderfiedTooltips(event, map);

  assert.is(markers[0].tooltip.options.direction, 'right');
  assert.is(markers[1].tooltip.options.direction, 'left');
  assert.is(markers[0].tooltip.updateCount, 1);

  resetSpiderfiedTooltips(event);

  assert.is(markers[0].tooltip.options.direction, 'auto');
  assert.is(markers[1].tooltip.options.direction, 'auto');
  assert.is(markers[0].tooltip._rundataOriginalDirection, undefined);
  assert.is(markers[0].tooltip.updateCount, 2);
});


test('inscriptions2markers() on empty input', async () => {
  const result = inscriptions2markers(new Map(), mockLeaflet);
  assert.is(result.size, 0, `The resulting object should be empty`);
});

test('inscriptions2markers() on one item', async () => {
  const myDb = new Map();
  myDb.set(1, {
    signature_text: "Test",
    id: 1,
    latitude: 1.0,
    longitude: 1.0,
    present_latitude: 10.0,
    present_longitude: 12.0,
  });
  const result = inscriptions2markers(myDb, mockLeaflet);
  assert.is(result.size, 1, `The resulting object should contain one item`);
  assert.is(result.has(1), true, `The resulting object should contain key 1`);
  const marker = result.get(1);

  assert.ok(marker.found, `The found marker should not be null`);
  assert.ok(marker.present, `The present marker should not be null`);
  
  assert.is(marker.found.getLatLng().lat, 1.0, `The found marker latitude should be 1.0`);
  assert.is(marker.found.getLatLng().lng, 1.0, `The found marker longitude should be 1.0`);
  assert.is(marker.present.getLatLng().lat, 10.0, `The present marker latitude should be 10.0`);
  assert.is(marker.present.getLatLng().lng, 12.0, `The present marker longitude should be 12.0`);
});

test('inscriptions2markers() on item without present location', async () => {
  const myDb = new Map();
  myDb.set(1, {
    signature_text: "Test",
    id: 1,
    latitude: 1.0,
    longitude: 1.0,
    present_latitude: 0.0,
    present_longitude: 0.0,
  });
  const result = inscriptions2markers(myDb, mockLeaflet);
  assert.is(result.size, 1, `The resulting object should contain one item`);
  const marker = result.get(1);

  assert.ok(marker.found, `The found marker should not be null`);
  assert.ok(marker.present, `The present marker should not be null`);
  assert.is(marker.present.getLatLng().lat, 1.0, `The present marker latitude should be 1.0`);
  assert.is(marker.present.getLatLng().lng, 1.0, `The present marker longitude should be 1.0`);
  assert.is(marker.found.getLatLng().lat, 1.0, `The found marker latitude should be 1.0`);
  assert.is(marker.found.getLatLng().lng, 1.0, `The found marker longitude should be 1.0`);
});

test('inscriptions2markers() on two items', async () => {
  const myDb = new Map();
  myDb.set(1, {
    signature_text: "Test",
    id: 1,
    latitude: 1.0,
    longitude: 1.0,
    present_latitude: 10.0,
    present_longitude: 12.0,
  });
  myDb.set(2, {
    signature_text: "Test2",
    id: 2,
    latitude: 2.0,
    longitude: 2.0,
    present_latitude: 20.0,
    present_longitude: 22.0,
  });
  const result = inscriptions2markers(myDb, mockLeaflet);
  assert.is(result.size, 2, `The resulting object should contain two items`);
});

test('inscriptions2markers() adds drive link and warnings to marker popup', async () => {
  const myDb = new Map();
  myDb.set(1, {
    signature_text: "Moved lost test",
    id: 1,
    latitude: 1.0,
    longitude: 1.0,
    present_latitude: 10.0,
    present_longitude: 12.0,
    current_location: "Museum",
    lost: true,
  });

  const result = inscriptions2markers(myDb, mockLeaflet);
  const marker = result.get(1).found;
  const presentMarker = result.get(1).present;

  assert.match(marker.popupText, /Warning: this inscription is lost/);
  assert.match(marker.popupText, /Warning: this inscription is moved/);
  assert.match(marker.popupText, /Drive here!/);
  assert.match(marker.popupText, /google\.com\/maps\/dir/);
  assert.is(marker.popupOptions.autoClose, false);
  assert.is(marker.popupOptions.autoPan, undefined);
  assert.not.match(marker.popupText, /map-drive-link/);
  assert.not.match(marker.popupText, /map-open-info-link/);
  assert.not.match(marker.popupText, /map-popup-warning/);
  assert.not.match(presentMarker.popupText, /Warning: this inscription is moved/);
  assert.not.match(presentMarker.popupText, /You are driving to Current location/);
  assert.is(marker.tooltipOptions.interactive, undefined);
  assert.is(marker.tooltipElement.attributes.role, undefined);
});

test('inscriptions2markers() uses mobile-only popup helpers on mobile', async () => {
  const originalNavigator = globalThis.navigator;
  Object.defineProperty(globalThis, 'navigator', {
    value: { userAgent: 'iPhone' },
    configurable: true,
  });

  const myDb = new Map();
  myDb.set(1, {
    signature_text: "Mobile moved test",
    id: 1,
    latitude: 1.0,
    longitude: 1.0,
    present_latitude: 10.0,
    present_longitude: 12.0,
    current_location: "Museum",
  });

  const result = inscriptions2markers(myDb, mockLeaflet);
  const marker = result.get(1).found;
  const presentMarker = result.get(1).present;

  assert.match(marker.popupText, /map-drive-link/);
  assert.match(marker.popupText, /map-open-info-link/);
  assert.match(marker.popupText, /Open info/);
  assert.match(marker.popupText, /openMobileInscriptionInfo\("1"\)/);
  assert.match(marker.popupText, /map-popup-warning/);
  assert.is(marker.popupOptions.autoPan, true);
  assert.match(presentMarker.popupText, /Warning: this inscription is moved/);
  assert.match(presentMarker.popupText, /You are driving to Current location/);
  assert.match(presentMarker.popupText, /map-popup-note/);
  assert.not.match(marker.popupText, /You are driving to Current location/);
  assert.is(marker.tooltipOptions.interactive, true);
  assert.is(marker.tooltipOptions.className, 'mobile-map-id-tooltip');
  assert.is(marker.tooltipElement.attributes.role, 'button');
  assert.is(marker.tooltipElement.attributes.tabindex, '0');
  marker.tooltipElement.listeners.click({
    preventDefault: () => {},
    stopPropagation: () => {},
  });
  assert.is(marker.openPopupCalled, true);

  Object.defineProperty(globalThis, 'navigator', {
    value: originalNavigator,
    configurable: true,
  });
});

test('openMobileInscriptionInfo() selects inscription before opening Info pane', () => {
  const originalNavigator = globalThis.navigator;
  const originalWindow = globalThis.window;
  const originalDocument = globalThis.document;
  let selectedId = null;
  let infoClicked = false;

  Object.defineProperty(globalThis, 'navigator', {
    value: {userAgent: 'iPhone'},
    configurable: true,
  });
  globalThis.window = {
    matchMedia: () => ({matches: true}),
    scrollToInscription: (_signature, inscriptionId) => {
      selectedId = inscriptionId;
    },
  };
  globalThis.document = {
    getElementById: (id) => id === 'mobilePaneInfo'
      ? {click: () => { infoClicked = true; }}
      : null,
  };

  const result = openMobileInscriptionInfo('42');

  assert.is(result, false);
  assert.is(selectedId, '42');
  assert.is(infoClicked, true);

  Object.defineProperty(globalThis, 'navigator', {
    value: originalNavigator,
    configurable: true,
  });
  globalThis.window = originalWindow;
  globalThis.document = originalDocument;
});
