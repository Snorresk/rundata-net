// Regression tests for inscriptions2markup rendering.
//
// Motivation: a normalization word search produces matchDetails.wordIndices
// but no fieldRanges. The render loop iterates over every user-selected field
// that has highlight: true. Translation columns (english_translation /
// swedish_translation) are also highlight-eligible but do NOT have any
// `<column>_word_boundaries` precomputed, so accessing `.filter` on
// `undefined` used to throw:
//
//   Error rendering signatures: TypeError: can't access property "filter",
//   e is undefined
//
// This test reproduces that scenario and guards against regressions.

import { test } from 'uvu';
import * as assert from 'uvu/assert';

const { inscriptions2markup, schemaFieldsInfo } = await import('../../runes/js/index_scripts.js');

// Install jQuery + getUserSelectedFields stubs before each test because other
// test files in the same uvu process (e.g. index_query_builder via
// setup-mocks.js) may overwrite the global `$`.
test.before.each(() => {
  global.$ = global.jQuery = function () {
    return { is: () => false };
  };
  global.window = {
    matchMedia: () => ({ matches: false }),
  };

  // index_scripts.js calls getUserSelectedFields() as a global (resolved via
  // the rollup bundle in production). In unit tests we stub it directly so
  // that inscriptions2markup can be exercised in isolation.
  global.getUserSelectedFields = function () {
    // Use the real schema entries so highlight/css/text metadata matches
    // production, including english_translation / swedish_translation which
    // are highlight-eligible but have no *_word_boundaries.
    const names = [
      'signature_text',
      'transliteration',
      'normalisation_norse',
      'english_translation',
    ];
    return names.map(n => schemaFieldsInfo.find(f => f.schemaName === n));
  };
});

function makeInscription(overrides = {}) {
  const base = {
    id: 1,
    signature_text: 'U 1',
    signature_header: 'U 1',
    signature_display: 'U 1',
    transliteration: 'kar stin',
    transliteration_html: 'kar stin',
    transliteration_word_boundaries: [
      { start: 0, end: 3, text: 'kar' },
      { start: 4, end: 8, text: 'stin' },
    ],
    normalisation_norse: 'gerði stein',
    normalisation_norse_html: 'gerði stein',
    normalisation_norse_word_boundaries: [
      { start: 0, end: 5, text: 'gerði' },
      { start: 6, end: 11, text: 'stein' },
    ],
    normalisation_scandinavian: 'gerde sten',
    normalisation_scandinavian_html: 'gerde sten',
    normalisation_scandinavian_word_boundaries: [
      { start: 0, end: 5, text: 'gerde' },
      { start: 6, end: 10, text: 'sten' },
    ],
    english_translation: 'made this stone',
    swedish_translation: 'gjorde denna sten',
    directImages: '',
    indirectImages: '',
    num_crosses: 0,
    crosses: [],
  };
  return Object.assign(base, overrides);
}

test('inscriptions2markup does not throw when translation columns are highlight-eligible but lack _word_boundaries', () => {
  // Simulate a normalization word search: matchDetails has wordIndices but no
  // fieldRanges. The default selected display includes english_translation
  // which has highlight: true but no word boundaries.
  const inscription = makeInscription({
    matchDetails: {
      wordIndices: [0],
    },
  });

  let html;
  try {
    html = inscriptions2markup([inscription]);
  } catch (e) {
    assert.unreachable(`inscriptions2markup threw: ${e && e.stack || e}`);
  }

  const joined = html.join('');
  // english_translation text still rendered (just not word-highlighted).
  assert.ok(joined.includes('made this stone'),
    'english_translation content should still be rendered');
  // normalization word highlight should be applied on the matched word.
  assert.ok(joined.includes('<span class="highlight">gerði</span>'),
    'matched normalization word should be highlighted');
});

test('inscriptions2markup hides empty mobile-only detail headers on mobile', () => {
  global.$ = global.jQuery = function () {
    return { is: () => true };
  };
  global.window = {
    matchMedia: () => ({ matches: true }),
  };
  global.getUserSelectedFields = function () {
    const names = [
      'signature_text',
      'lost',
      'rune_type',
      'num_crosses',
      'cross_form',
    ];
    return names.map(n => schemaFieldsInfo.find(f => f.schemaName === n));
  };

  const inscription = makeInscription({
    lost: 0,
    rune_type: '',
    num_crosses: 0,
    cross_form: '',
  });
  const joined = inscriptions2markup([inscription]).join('');

  assert.ok(joined.includes('<h4>Inscription ID</h4>'),
    'non-empty default header should still be rendered');
  assert.not.ok(joined.includes('<h4>Is Lost?</h4>'),
    'false lost value should be hidden on mobile');
  assert.not.ok(joined.includes('<h4>Rune type</h4>'),
    'empty rune type should be hidden on mobile');
  assert.not.ok(joined.includes('<h4>Number of crosses</h4>'),
    'zero cross count should be hidden on mobile');
  assert.not.ok(joined.includes('<h4>Cross form</h4>'),
    'empty cross form should be hidden on mobile');
});

test.run();
