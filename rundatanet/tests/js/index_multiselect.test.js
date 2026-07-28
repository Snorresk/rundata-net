import { test } from 'uvu';
import * as assert from 'uvu/assert';

// Mock jQuery with option tracking for multiselect DOM elements
function createMultiselectMock(rightOptions, leftOptions) {
  // Each option is { value, sortValue }
  const makeJqOption = (opt) => ({
    attr: (name, value) => {
      if (value !== undefined) {
        opt[name] = value;
      }
      return opt[name];
    }
  });

  const makeJqCollection = (options) => ({
    each: function(fn) {
      options.forEach((opt, i) => {
        // 'this' inside jQuery .each() is the element — simulate with the jq wrapper
        fn.call(makeJqOption(opt), i, opt);
      });
    }
  });

  // Mock $ function that responds to multiselect selectors
  const $ = (selector) => {
    if (selector === '#multiselect_to option') return makeJqCollection(rightOptions);
    if (selector === '#multiselect option') return makeJqCollection(leftOptions);
    // When called as $(this) inside .each, 'this' is already a jq wrapper
    if (selector && typeof selector.attr === 'function') return selector;
    return { attr: () => {} };
  };
  return $;
}

// Override global $ for the module under test
import { getUserSelectedDisplay, resortDisplayOptions } from '../../runes/js/index_multiselect.js';

function createLocalStorageMock(initialValues = {}) {
  const values = new Map(Object.entries(initialValues));
  return {
    get length() {
      return values.size;
    },
    getItem: key => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  };
}

test('resortDisplayOptions() assigns sequential sortValues, right list first', () => {
  const rightOptions = [
    { value: 'transliteration', sortValue: 5 },
    { value: 'signature_text', sortValue: 0 },
    { value: 'images', sortValue: 10 },
  ];
  const leftOptions = [
    { value: 'parish', sortValue: 3 },
    { value: 'found_location', sortValue: 2 },
  ];

  global.$ = createMultiselectMock(rightOptions, leftOptions);

  resortDisplayOptions();

  // Right (selected) options should be numbered 0, 1, 2
  assert.is(rightOptions[0].sortValue, 0, 'First right option should have sortValue 0');
  assert.is(rightOptions[1].sortValue, 1, 'Second right option should have sortValue 1');
  assert.is(rightOptions[2].sortValue, 2, 'Third right option should have sortValue 2');

  // Left (available) options should continue from 3
  assert.is(leftOptions[0].sortValue, 3, 'First left option should have sortValue 3');
  assert.is(leftOptions[1].sortValue, 4, 'Second left option should have sortValue 4');
});

test('resortDisplayOptions() with empty right list starts left from 0', () => {
  const rightOptions = [];
  const leftOptions = [
    { value: 'a', sortValue: 99 },
    { value: 'b', sortValue: 50 },
  ];

  global.$ = createMultiselectMock(rightOptions, leftOptions);

  resortDisplayOptions();

  assert.is(leftOptions[0].sortValue, 0, 'First left option should have sortValue 0');
  assert.is(leftOptions[1].sortValue, 1, 'Second left option should have sortValue 1');
});

test('resortDisplayOptions() with empty left list numbers only right', () => {
  const rightOptions = [
    { value: 'x', sortValue: 10 },
    { value: 'y', sortValue: 20 },
  ];
  const leftOptions = [];

  global.$ = createMultiselectMock(rightOptions, leftOptions);

  resortDisplayOptions();

  assert.is(rightOptions[0].sortValue, 0, 'First right option should have sortValue 0');
  assert.is(rightOptions[1].sortValue, 1, 'Second right option should have sortValue 1');
});

test('resortDisplayOptions() with both lists empty does nothing', () => {
  global.$ = createMultiselectMock([], []);
  // Should not throw
  resortDisplayOptions();
});

test('resortDisplayOptions() preserves order after simulated reorder', () => {
  // Simulate: user moved option at index 2 up to index 0 (reordered)
  // Before resort, sortValues are out of sequence
  const rightOptions = [
    { value: 'images', sortValue: 10 },       // was at bottom, moved to top
    { value: 'signature_text', sortValue: 0 }, // shifted down
    { value: 'transliteration', sortValue: 5 },// shifted down
  ];
  const leftOptions = [
    { value: 'parish', sortValue: 3 },
  ];

  global.$ = createMultiselectMock(rightOptions, leftOptions);

  resortDisplayOptions();

  // After resort, sortValues should be sequential and match current positions
  assert.is(rightOptions[0].sortValue, 0, 'images (now first) should have sortValue 0');
  assert.is(rightOptions[1].sortValue, 1, 'signature_text (now second) should have sortValue 1');
  assert.is(rightOptions[2].sortValue, 2, 'transliteration (now third) should have sortValue 2');
  assert.is(leftOptions[0].sortValue, 3, 'parish should have sortValue 3');

  // Verify that a sort by sortValue would preserve the reordered positions
  const sorted = [...rightOptions].sort((a, b) => a.sortValue - b.sortValue);
  assert.is(sorted[0].value, 'images', 'After sort, images should remain first');
  assert.is(sorted[1].value, 'signature_text', 'After sort, signature_text should remain second');
  assert.is(sorted[2].value, 'transliteration', 'After sort, transliteration should remain third');
});

test('getUserSelectedDisplay() respects saved display choices without coordinates', () => {
  global.window = {
    localStorage: createLocalStorageMock({
      userSelectedDisplay: JSON.stringify(['signature_text', 'transliteration']),
    }),
    matchMedia: () => ({ matches: false }),
    innerWidth: 1440,
    document: { documentElement: { clientWidth: 1440 } },
  };

  const selected = getUserSelectedDisplay();

  assert.equal(selected, ['signature_text', 'transliteration']);
});

test.run();
