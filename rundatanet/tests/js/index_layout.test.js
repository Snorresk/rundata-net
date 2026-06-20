import { test } from 'uvu';
import * as assert from 'uvu/assert';
import {
  COMPACT_DB_LAYOUT_MEDIA_QUERY,
  isCompactDbLayout,
} from '../../runes/js/index_layout.js';

function makeWindow({matches = false, innerWidth = 1024, touch = false} = {}) {
  const windowObject = {
    innerWidth,
    document: {documentElement: {clientWidth: innerWidth}},
    matchMedia: query => ({matches, media: query}),
  };
  if (touch) {
    windowObject.ontouchstart = () => {};
  }
  return windowObject;
}

function makeCapabilityWindow({innerWidth, coarsePointer}) {
  return {
    innerWidth,
    document: {documentElement: {clientWidth: innerWidth}},
    matchMedia: () => ({
      matches: innerWidth <= 767.98 || (innerWidth <= 1366 && coarsePointer),
    }),
  };
}

test('compact layout query covers phones and coarse-pointer tablets', () => {
  assert.ok(COMPACT_DB_LAYOUT_MEDIA_QUERY.includes('max-width: 767.98px'));
  assert.ok(COMPACT_DB_LAYOUT_MEDIA_QUERY.includes('max-width: 1366px'));
  assert.ok(COMPACT_DB_LAYOUT_MEDIA_QUERY.includes('any-pointer: coarse'));
  assert.is(isCompactDbLayout(makeWindow({matches: true})), true);
});

test('ordinary laptop width does not activate compact layout', () => {
  const windowObject = makeWindow({matches: false, innerWidth: 1024});
  const navigatorObject = {userAgent: 'Mozilla/5.0', platform: 'MacIntel', maxTouchPoints: 0};

  assert.is(isCompactDbLayout(windowObject, navigatorObject), false);
});

test('iPadOS Mac user-agent fallback activates at tablet width', () => {
  const windowObject = makeWindow({matches: false, innerWidth: 1366, touch: true});
  const navigatorObject = {userAgent: 'Mozilla/5.0 Macintosh Safari', platform: 'MacIntel', maxTouchPoints: 5};

  assert.is(isCompactDbLayout(windowObject, navigatorObject), true);
});

test('Android tablet fallback activates when pointer media is unavailable', () => {
  const windowObject = makeWindow({matches: false, innerWidth: 1280, touch: true});
  const navigatorObject = {userAgent: 'Mozilla/5.0 Android 14', platform: 'Linux armv8l', maxTouchPoints: 5};

  assert.is(isCompactDbLayout(windowObject, navigatorObject), true);
});

test('tablet fallback stays desktop above the supported width', () => {
  const windowObject = makeWindow({matches: false, innerWidth: 1440, touch: true});
  const navigatorObject = {userAgent: 'Mozilla/5.0 iPad', platform: 'MacIntel', maxTouchPoints: 5};

  assert.is(isCompactDbLayout(windowObject, navigatorObject), false);
});

test('iPad and Android tablet viewport matrix uses compact layout', () => {
  const tabletViewports = [
    {name: 'iPad Air portrait', width: 820},
    {name: 'iPad Air landscape', width: 1180},
    {name: 'iPad Pro 13 landscape', width: 1366},
    {name: 'Android tablet portrait', width: 800},
    {name: 'Android tablet landscape', width: 1280},
  ];

  tabletViewports.forEach(({name, width}) => {
    assert.is(
      isCompactDbLayout(makeCapabilityWindow({innerWidth: width, coarsePointer: true})),
      true,
      name
    );
  });
});

test('fine-pointer desktops keep desktop layout at tablet-like widths', () => {
  [768, 1024, 1180, 1366, 1440].forEach(width => {
    assert.is(
      isCompactDbLayout(makeCapabilityWindow({innerWidth: width, coarsePointer: false})),
      false,
      `desktop width ${width}`
    );
  });
});

test.run();
