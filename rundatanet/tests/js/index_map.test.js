import { test } from 'uvu';
import * as assert from 'uvu/assert';
import { inscriptions2markers } from '../../runes/js/index_map.js';

const mockLeaflet = {
  marker: (latlng, options) => {
      const markerObj = {
        _latlng: latlng,
        options: options,
        getLatLng: () => {
          return {
            lat: latlng[0],
            lng: latlng[1]
          }
        },
        bindPopup: () => markerObj,
        bindTooltip: () => markerObj,
        openTooltip: () => markerObj,
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
