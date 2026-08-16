import { test } from 'uvu';
import * as assert from 'uvu/assert';
import {
  applyPublicationMapBoundsZoom,
  buildPublicationMapPngBlob,
  buildPublicationMapSvg,
  choosePublicationMapOsmZoom,
  expandPublicationMapBoundsToAspect,
  getPublicationMapOsmTileLayout,
  getPublicationMapCoordinate,
  getMarkerClusterOptions,
  getSpiderfiedTooltipDirection,
  handleMobileClusterClick,
  inscriptions2markers,
  openMobileInscriptionInfo,
  positionSpiderfiedTooltips,
  resetSpiderfiedTooltips,
  showMarkers,
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

test('showMarkers() sizes the map before fitting all visible inscriptions', () => {
  const marker = {getLatLng: () => ({lat: 58, lng: 15})};
  const markersLayer = {
    clearLayers: () => {},
    addLayers: () => {},
  };
  const mapObject = {
    invalidateSize: options => { mapObject.invalidateOptions = options; },
    fitBounds: (bounds, options) => {
      mapObject.fittedBounds = bounds;
      mapObject.fitOptions = options;
    },
  };

  showMarkers({
    inscriptionIds: [1],
    allMarkers: new Map([[1, {found: marker, present: marker}]]),
    mapObject,
    markersLayer,
  });

  assert.equal(mapObject.invalidateOptions, {pan: false});
  assert.equal(mapObject.fittedBounds, [{lat: 58, lng: 15}]);
  assert.equal(mapObject.fitOptions, {padding: [20, 20]});
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
  assert.match(marker.popupText, /target="_blank"/);
  assert.match(marker.popupText, /rel="noopener"/);
  assert.not.match(marker.popupText, /target="_self"/);
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
  const originalWindow = globalThis.window;
  Object.defineProperty(globalThis, 'navigator', {
    value: { userAgent: 'iPhone' },
    configurable: true,
  });
  globalThis.window = {
    matchMedia: () => ({matches: true}),
  };

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
  assert.match(marker.popupText, /target="_blank"/);
  assert.match(marker.popupText, /rel="noopener"/);
  assert.not.match(marker.popupText, /target="_self"/);
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
  globalThis.window = originalWindow;
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

test('getPublicationMapCoordinate() prefers current location and falls back to original', () => {
  const inscription = {
    latitude: 59.5,
    longitude: 17.8,
    present_latitude: 0,
    present_longitude: 0,
  };

  assert.equal(getPublicationMapCoordinate(inscription, 'current'), {
    lat: 59.5,
    lon: 17.8,
    source: 'original',
  });
  assert.equal(getPublicationMapCoordinate({
    ...inscription,
    present_latitude: 58.4,
    present_longitude: 15.6,
  }, 'current'), {
    lat: 58.4,
    lon: 15.6,
    source: 'current',
  });
});

test('buildPublicationMapSvg() creates editable SVG symbols from inscriptions', () => {
  const result = buildPublicationMapSvg([
    {
      id: 1,
      signature_text: 'U 1',
      latitude: 59.4,
      longitude: 17.8,
      present_latitude: 59.4,
      present_longitude: 17.8,
    },
    {
      id: 2,
      signature_text: 'U 2',
      latitude: 60.0,
      longitude: 18.2,
      present_latitude: 0,
      present_longitude: 0,
    },
    {
      id: 3,
      signature_text: 'No coordinates',
      latitude: 0,
      longitude: 0,
      present_latitude: 0,
      present_longitude: 0,
    },
  ], {
    groupName: 'Test group',
    symbol: 'triangle',
    symbolColour: '#cc0000',
  });

  assert.is(result.pointCount, 2);
  assert.is(result.skippedCount, 1);
  assert.match(result.svg, /<svg /);
  assert.match(result.svg, /Test group/);
  assert.match(result.svg, /<polygon class="inscription-symbol"/);
  assert.match(result.svg, /fill="#cc0000"/);
  assert.match(result.svg, /U 1/);
  assert.match(result.svg, /To publish or present this map, specify its source: https:\/\/rundata\.info\./);
});

test('buildPublicationMapSvg() wraps long source captions inside the page', () => {
  const result = buildPublicationMapSvg([
    {
      id: 1,
      signature_text: 'U 1',
      latitude: 59.4,
      longitude: 17.8,
      present_latitude: 59.4,
      present_longitude: 17.8,
    },
  ], {
    width: 600,
    height: 450,
  });

  const captionTspans = result.svg.match(/<tspan x="82" y="\d+">/g) || [];
  assert.ok(captionTspans.length > 1);
  assert.match(result.svg, /Coordinates exported from Rundata-net/);
  assert.match(result.svg, /https:\/\/rundata\.info\./);
});

test('buildPublicationMapPngBlob() draws map tiles and symbols on canvas', async () => {
  const originalDocument = globalThis.document;
  const originalImage = globalThis.Image;
  const originalFileReader = globalThis.FileReader;
  const calls = [];
  const canvasContext = {
    scale: (...args) => calls.push(['scale', ...args]),
    fillRect: (...args) => calls.push(['fillRect', ...args]),
    save: () => calls.push(['save']),
    restore: () => calls.push(['restore']),
    beginPath: () => calls.push(['beginPath']),
    rect: (...args) => calls.push(['rect', ...args]),
    clip: () => calls.push(['clip']),
    drawImage: (...args) => calls.push(['drawImage', ...args]),
    strokeRect: (...args) => calls.push(['strokeRect', ...args]),
    fillText: (...args) => calls.push(['fillText', ...args]),
    arc: (...args) => calls.push(['arc', ...args]),
    moveTo: (...args) => calls.push(['moveTo', ...args]),
    lineTo: (...args) => calls.push(['lineTo', ...args]),
    closePath: () => calls.push(['closePath']),
    fill: () => calls.push(['fill']),
    stroke: () => calls.push(['stroke']),
    quadraticCurveTo: (...args) => calls.push(['quadraticCurveTo', ...args]),
    set fillStyle(value) { calls.push(['fillStyle', value]); },
    set strokeStyle(value) { calls.push(['strokeStyle', value]); },
    set lineWidth(value) { calls.push(['lineWidth', value]); },
    set globalAlpha(value) { calls.push(['globalAlpha', value]); },
    set font(value) { calls.push(['font', value]); },
  };

  globalThis.document = {
    createElement: (tagName) => {
      assert.is(tagName, 'canvas');
      return {
        width: 0,
        height: 0,
        getContext: () => canvasContext,
        toBlob: callback => callback(new Blob(['png'], {type: 'image/png'})),
      };
    },
  };
  globalThis.Image = class {
    set src(value) {
      this._src = value;
      setTimeout(() => this.onload && this.onload(), 0);
    }
    get src() {
      return this._src;
    }
  };
  globalThis.FileReader = class {
    readAsDataURL() {
      this.result = 'data:image/png;base64,dGlsZQ==';
      setTimeout(() => this.onload && this.onload(), 0);
    }
  };

  try {
    const result = await buildPublicationMapPngBlob([{
      id: 1,
      signature_text: 'U 1',
      latitude: 59.4,
      longitude: 17.8,
      present_latitude: 59.4,
      present_longitude: 17.8,
    }], {
      width: 600,
      height: 450,
      pngScale: 1,
      fetchTile: async () => ({
        ok: true,
        blob: async () => new Blob(['tile'], {type: 'image/png'}),
      }),
    });

    assert.is(result.pointCount, 1);
    assert.is(result.blob.type, 'image/png');
    assert.ok(calls.some(call => call[0] === 'drawImage'));
    assert.ok(calls.some(call => call[0] === 'arc'));
  } finally {
    globalThis.document = originalDocument;
    globalThis.Image = originalImage;
    globalThis.FileReader = originalFileReader;
  }
});

test('buildPublicationMapSvg() allows smaller symbols and clamps oversized symbols', () => {
  const inscriptions = [
    {
      id: 1,
      signature_text: 'U 1',
      latitude: 59.4,
      longitude: 17.8,
      present_latitude: 59.4,
      present_longitude: 17.8,
    },
  ];

  const small = buildPublicationMapSvg(inscriptions, {
    symbol: 'dot',
    symbolSize: 3,
  });
  const oversized = buildPublicationMapSvg(inscriptions, {
    symbol: 'dot',
    symbolSize: 20,
  });

  assert.match(small.svg, / r="3\.0"/);
  assert.match(oversized.svg, / r="6\.0"/);
});

test('buildPublicationMapSvg() creates grouped publication maps', () => {
  const result = buildPublicationMapSvg([], {
    groups: [
      {
        groupName: 'Opir Pr 3',
        symbol: 'dot',
        symbolColour: '#d62728',
        symbolSize: 4,
        inscriptions: [{
          id: 1,
          signature_text: 'U 1',
          latitude: 59.4,
          longitude: 17.8,
          present_latitude: 59.4,
          present_longitude: 17.8,
        }],
      },
      {
        groupName: 'Opir Pr 4',
        symbol: 'square',
        symbolColour: '#1f77b4',
        symbolSize: 3,
        inscriptions: [{
          id: 2,
          signature_text: 'U 2',
          latitude: 59.7,
          longitude: 18.1,
          present_latitude: 59.7,
          present_longitude: 18.1,
        }],
      },
    ],
  });

  assert.is(result.pointCount, 2);
  assert.match(result.svg, /2 inscriptions in 2 groups/);
  assert.match(result.svg, /Opir Pr 3/);
  assert.match(result.svg, /Opir Pr 4/);
  assert.match(result.svg, /<circle class="inscription-symbol"/);
  assert.match(result.svg, /<rect class="inscription-symbol"/);
  assert.match(result.svg, /fill="#d62728"/);
  assert.match(result.svg, /fill="#1f77b4"/);
  assert.match(result.svg, /<rect class="legend-frame"/);
  assert.not.match(result.svg, /\.legend rect/);
});

test('getPublicationMapOsmTileLayout() keeps OSM tile export bounded', () => {
  const bounds = {
    minLat: 58.5,
    maxLat: 59.8,
    minLon: 16.5,
    maxLon: 18.8,
  };
  const zoom = choosePublicationMapOsmZoom(bounds);
  const layout = getPublicationMapOsmTileLayout(bounds);

  assert.ok(zoom >= 3);
  assert.ok(zoom <= 14);
  assert.ok(layout.tiles.length > 0);
  assert.ok(layout.tiles.length <= 80);
  assert.match(layout.tiles[0].url, /^https:\/\/tile\.openstreetmap\.org\/\d+\/\d+\/\d+\.png$/);
});

test('getPublicationMapOsmTileLayout() supports the publication basemap provider', () => {
  const bounds = {
    minLat: 58.5,
    maxLat: 59.8,
    minLon: 16.5,
    maxLon: 18.8,
  };
  const layout = getPublicationMapOsmTileLayout(bounds, 1200, 900, 'carto-positron');

  assert.is(layout.provider.name, 'CARTO Positron');
  assert.ok(layout.tiles.length > 0);
  assert.match(layout.tiles[0].url, /^https:\/\/a\.basemaps\.cartocdn\.com\/light_all\/\d+\/\d+\/\d+\.png$/);
});

test('applyPublicationMapBoundsZoom() changes map extent without hiding points', () => {
  const bounds = {
    minLat: 58.4,
    maxLat: 60.2,
    minLon: 16.1,
    maxLon: 19.2,
  };
  const points = [
    {lat: 58.9, lon: 17.0},
    {lat: 59.7, lon: 18.3},
  ];
  const zoomedIn = applyPublicationMapBoundsZoom(bounds, points, 2);
  const zoomedOut = applyPublicationMapBoundsZoom(bounds, points, -2);

  assert.ok(zoomedIn.maxLon - zoomedIn.minLon < bounds.maxLon - bounds.minLon);
  assert.ok(zoomedIn.minLat < 58.9);
  assert.ok(zoomedIn.maxLat > 59.7);
  assert.ok(zoomedIn.minLon < 17.0);
  assert.ok(zoomedIn.maxLon > 18.3);
  assert.ok(zoomedOut.maxLon - zoomedOut.minLon > bounds.maxLon - bounds.minLon);
  assert.ok(zoomedOut.maxLat - zoomedOut.minLat > bounds.maxLat - bounds.minLat);
});

test('publication map export expands narrow bounds to the page shape', () => {
  const narrowBounds = {
    minLat: 58.65,
    maxLat: 60.1,
    minLon: 17.2,
    maxLon: 17.85,
  };

  const framedBounds = expandPublicationMapBoundsToAspect(narrowBounds);
  const layout = getPublicationMapOsmTileLayout(narrowBounds);

  assert.ok(framedBounds.minLon < narrowBounds.minLon);
  assert.ok(framedBounds.maxLon > narrowBounds.maxLon);
  assert.ok(layout.projection.mapRect.width > 1000);
  assert.ok(layout.projection.mapRect.height > 720);
});
