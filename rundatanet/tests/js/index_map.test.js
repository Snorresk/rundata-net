import { test } from 'uvu';
import * as assert from 'uvu/assert';
import { inscriptions2markers } from '../../runes/js/index_map.js';

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
