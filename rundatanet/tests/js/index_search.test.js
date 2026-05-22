import { test } from 'uvu';
import * as assert from 'uvu/assert';
import { doSearch, stripSpecialSymbols, getWordSearchFunction, getTranslationSearchTokens, getTranslationSearchTokenCount, getTranslationOccurrenceCount, shouldSuggestIncludeSymbols } from '../../runes/js/index_search.js';
import { mockDb } from './mockDb.js';
import { convertDbToKeyMap, highlightWordsFromWordBoundaries } from '../../runes/js/index_scripts.js';

// Process mockDb once at the module level
const dbMap = convertDbToKeyMap(mockDb);

test('getTranslationSearchTokens collects tokens from English/Swedish translation rules', () => {
  const rules = {
    condition: 'AND',
    rules: [
      {
        id: 'english_translation',
        field: 'english_translation',
        operator: 'contains',
        value: 'king stone',
      },
      {
        id: 'swedish_translation',
        field: 'swedish_translation',
        operator: 'begins_with',
        value: 'sten, konung',
      },
      {
        id: 'signature_text',
        field: 'signature_text',
        operator: 'contains',
        value: 'DR',
      }
    ],
    valid: true
  };

  const tokens = getTranslationSearchTokens(rules);
  assert.equal(tokens, ['king', 'stone', 'sten', 'konung']);
  assert.is(getTranslationSearchTokenCount(rules), 4);
});

test('getTranslationSearchTokens ignores valueless translation operators', () => {
  const rules = {
    condition: 'AND',
    rules: [
      {
        id: 'english_translation',
        field: 'english_translation',
        operator: 'is_not_empty',
        value: null,
      },
      {
        id: 'swedish_translation',
        field: 'swedish_translation',
        operator: 'is_empty',
        value: null,
      }
    ],
    valid: true
  };

  assert.equal(getTranslationSearchTokens(rules), []);
  assert.is(getTranslationSearchTokenCount(rules), 0);
});

test('getTranslationOccurrenceCount sums translation field match ranges', () => {
  const mockResults = [
    {
      matchDetails: {
        fieldRanges: {
          english_translation: [[0, 4], [10, 14]],
          swedish_translation: [[2, 6]],
        }
      }
    },
    {
      matchDetails: {
        fieldRanges: {
          english_translation: [[1, 5]],
        }
      }
    },
    {
      matchDetails: {
        fieldRanges: {
          signature_text: [[0, 2]],
        }
      }
    },
    {}
  ];

  assert.is(getTranslationOccurrenceCount(mockResults), 4);
});

test('shouldSuggestIncludeSymbols returns true for symbol query when include symbols is off', () => {
  const rules = {
    condition: 'AND',
    rules: [{
      id: 'normalization_norse_to_transliteration',
      field: 'normalisation_norse',
      data: { multiField: true },
      operator: 'contains',
      value: { normalization: '?', transliteration: '', names_mode: 'all' },
      includeSpecialSymbols: false,
    }],
    valid: true,
  };

  assert.ok(shouldSuggestIncludeSymbols(rules));
});

test('shouldSuggestIncludeSymbols returns false when include symbols is on', () => {
  const rules = {
    condition: 'AND',
    rules: [{
      id: 'normalization_norse_to_transliteration',
      field: 'normalisation_norse',
      operator: 'contains',
      value: { normalization: '?', transliteration: '', names_mode: 'all' },
      includeSpecialSymbols: true,
    }],
    valid: true,
  };

  assert.not.ok(shouldSuggestIncludeSymbols(rules));
});

// Test suite for highlightWordsFromWordBoundaries function
test('highlightWordsFromWordBoundaries with single word', () => {
  const str = 'This is a test string';
  const wordBoundaries = [
    { start: 5, end: 7, text: 'is' }
  ];
  const result = highlightWordsFromWordBoundaries(str, wordBoundaries);
  const expected = 'This <span class="highlight">is</span> a test string';
  assert.is(result, expected, 'Should highlight a single word correctly');
});

test('highlightWordsFromWordBoundaries with multiple words', () => {
  const str = 'Testing multiple words in this string';
  const wordBoundaries = [
    { start: 0, end: 7, text: 'Testing' },
    { start: 17, end: 22, text: 'words' },
    { start: 26, end: 30, text: 'this' }
  ];
  const result = highlightWordsFromWordBoundaries(str, wordBoundaries);
  const expected = '<span class="highlight">Testing</span> multiple <span class="highlight">words</span> in <span class="highlight">this</span> string';
  assert.is(result, expected, 'Should highlight multiple words correctly');
});

test('highlightWordsFromWordBoundaries with unsorted boundaries', () => {
  const str = 'Words in random order';
  const words = ['order', 'Words', 'random'];
  const wordBoundaries = words.map(word => {
    const start = str.indexOf(word);
    const end = start + word.length;
    return { start, end, text: word };
  });

  const result = highlightWordsFromWordBoundaries(str, wordBoundaries);
  const expected = '<span class="highlight">Words</span> in <span class="highlight">random</span> <span class="highlight">order</span>';
  assert.is(result, expected, 'Should sort boundaries and highlight words correctly');
});

test('highlightWordsFromWordBoundaries with adjacent words', () => {
  const str = 'Adjacent words test';
  const wordBoundaries = [
    { start: 0, end: 8, text: 'Adjacent' },
    { start: 9, end: 14, text: 'words' }
  ];
  const result = highlightWordsFromWordBoundaries(str, wordBoundaries);
  const expected = '<span class="highlight">Adjacent</span> <span class="highlight">words</span> test';
  assert.is(result, expected, 'Should highlight adjacent words correctly');
});

test('highlightWordsFromWordBoundaries with empty string', () => {
  const str = '';
  const wordBoundaries = [
    { start: 0, end: 0, text: '' }
  ];
  const result = highlightWordsFromWordBoundaries(str, wordBoundaries);
  const expected = '<span class="highlight"></span>';
  assert.is(result, expected, 'Should handle empty string correctly');
});

test('highlightWordsFromWordBoundaries with no boundaries', () => {
  const str = 'No boundaries to highlight';
  const wordBoundaries = [];
  const result = highlightWordsFromWordBoundaries(str, wordBoundaries);
  const expected = 'No boundaries to highlight';
  assert.is(result, expected, 'Should return original string when no boundaries are provided');
});


// Helper function to create a readable string representation of the search value
function getValueAsString(value) {
  if (value === null) {
    return 'null';
  } else if (Array.isArray(value)) {
    return '[' + value.map(v => `"${v}"`).join(', ') + ']';
  } else if (typeof value === 'object') {
    return JSON.stringify(value);
  } else {
    return `"${value}"`;
  }
}

/**
 * Test function for searching inscriptions using a single rule
 *
 * @param {Object} options - The options for the search test
 * @param {string} options.operator - The operator to use for the search rule (e.g., 'equal', 'contains')
 * @param {*} options.value - The value to search for
 * @param {number} options.expectedCount - The number of results expected to be found
 * @param {string} [options.testName] - Custom name for the test (defaults to a generated name using field and operator)
 * @param {string|null} [options.id] - Custom id for the rule (defaults to field name)
 * @param {*} [options.firstResultCheck] - Value to check against the first result's field (if provided)
 * @param {boolean} [options.multiField=false] - Whether the search rule is multi-field or not
 * @param {string} [options.condition='AND'] - The condition to use for combining rules
 * @param {string} [options.field='signature_text'] - The field to search in
 * @returns {void}
 */
function testSingleRuleSearch({
  operator,
  value,
  expectedCount,
  testName,
  id = null,
  firstResultCheck = null,
  multiField = false,
  condition = 'AND',
  field = 'signature_text'
}) {
  test(testName || `search inscription via ${field}::${operator} (${getValueAsString(value)})`, () => {
    const rules = {
      condition: condition,
      rules: [
        {
          id: id || field,
          field: field,
          type: 'string',
          input: 'text',
          operator: operator,
          value: value,
          data: multiField ? { multiField: true } : {}
        }
      ],
      not: false,
      valid: true
    };

    const result = doSearch(rules, dbMap.values());

    assert.is(result.length, expectedCount, `Should find ${expectedCount} inscriptions`);

    if (firstResultCheck) {
      if (typeof firstResultCheck === 'object') {
        const fieldDataStr = JSON.stringify(result[0][field]);
        const firstResultCheckStr = JSON.stringify(firstResultCheck);
        assert.is(fieldDataStr, firstResultCheckStr, `First result should be ${firstResultCheckStr}`);
      } else {
        assert.is(result[0][field], firstResultCheck, `First result should be ${firstResultCheck}`);
      }
    }
  });
}

testSingleRuleSearch({
  id: 'inscription_id',
  operator: 'in',
  value: 'Öl 1',
  expectedCount: 1,
  testName: 'search one inscription',
  firstResultCheck: 'Öl 1',
  multiField: true,
});
testSingleRuleSearch({
  id: 'inscription_id',
  operator: 'in',
  value: ['Öl 1', 'Öl 2'],
  expectedCount: 2,
  testName: 'search multiple inscriptions by id',
  multiField: true,
});
testSingleRuleSearch({
  id: 'inscription_id',
  operator: 'in_separated_list',
  value: 'Öl 1|Öl 2|Öl 12',
  expectedCount: 3,
  multiField: true,
});
testSingleRuleSearch({
  id: 'inscription_id',
  operator: 'begins_with',
  value: 'Öl 1',
  expectedCount: 11,
  firstResultCheck: 'Öl 1',
  multiField: true,
});
testSingleRuleSearch({
  id: 'inscription_id',
  operator: 'not_begins_with',
  value: 'Öl 1',
  expectedCount: 6804,
  firstResultCheck: 'Öl 2',
  multiField: true,
});
testSingleRuleSearch({
  id: 'inscription_id',
  operator: 'ends_with',
  value: '4',
  expectedCount: 1026,
  firstResultCheck: 'Öl 2',
  multiField: true,
});
testSingleRuleSearch({
  id: 'inscription_id',
  operator: 'not_ends_with',
  value: '4',
  expectedCount: 5789,
  firstResultCheck: 'Öl 1',
  multiField: true,
});
testSingleRuleSearch({
  id: 'inscription_id',
  operator: 'contains',
  value: 'Öl',
  expectedCount: 190,
  firstResultCheck: 'Öl 1',
  multiField: true,
});
testSingleRuleSearch({
  id: 'inscription_id',
  operator: 'not_contains',
  value: 'Öl',
  expectedCount: 6625,
  firstResultCheck: 'Ög 1',
  multiField: true,
});


testSingleRuleSearch({
  id: 'inscription_country',
  field: 'signature_text',
  operator: 'in',
  value: ['Öl', 'Sm'],
  expectedCount: 385,
  firstResultCheck: 'Öl 1',
  multiField: true,
});
testSingleRuleSearch({
  id: 'inscription_country',
  field: 'signature_text',
  operator: 'in',
  value: ['all_sweden'],
  expectedCount: 4049,
  firstResultCheck: 'Öl 1',
  multiField: true,
});


testSingleRuleSearch({
  field: 'carver',
  operator: 'is_empty',
  value: null,
  expectedCount: 5735,
  firstResultCheck: '',
});
testSingleRuleSearch({
  field: 'carver',
  operator: 'is_not_empty',
  value: null,
  expectedCount: 1080,
  firstResultCheck: 'Nilsson attribuerar stenen till Korp.',
});
testSingleRuleSearch({
  field: 'carver',
  operator: 'equal',
  value: 'Nilsson attribuerar stenen till Korp.',
  expectedCount: 3,
  firstResultCheck: 'Nilsson attribuerar stenen till Korp.',
});


testSingleRuleSearch({
  id: 'cross_form',
  field: 'crosses',
  operator: 'cross_form',
  value: {
    form: 'B1',
    is_certain: "1",
  },
  expectedCount: 662,
  multiField: false,
  firstResultCheck: JSON.parse('[[[],[{"name":"A4","isCertain":1}],[{"name":"B1","isCertain":1}],[{"name":"C9","isCertain":1},{"name":"C10","isCertain":1}],[{"name":"D5","isCertain":1}],[{"name":"E5","isCertain":1}],[{"name":"F3","isCertain":1}],[]]]'),
});


testSingleRuleSearch({
  field: 'year_from',
  operator: 'equal',
  value: 1100,
  expectedCount: 1876,
  multiField: false,
  firstResultCheck: 1100,
});

test('search inscription via year range', () => {
  const multiField = false;
  const rules = {
    condition: "AND",
    rules: [
      {
        id: "year_from",
        field: "year_from",
        operator: "greater",
        value: 1099,
        data: multiField ? { multiField: true } : {}
      },
      {
        id: "year_to",
        field: "year_to",
        operator: "less",
        value: 1101,
        data: multiField ? { multiField: true } : {}
      },
    ],
    not: false,
    valid: true
  };

  const results = doSearch(rules, dbMap.values());
  const expectedCount = 48;

  assert.not(results[0].signature_text === 'Ög 218', 'Should not find Ög 218');
  assert.is(results.length, expectedCount, `Should find ${expectedCount} inscriptions`);
});

// Test for style search - Issue: "Öl 4" has style "Pr 4" but search for "begins_with Pr 4" doesn't find it
test('search by style begins_with Pr 4 should find Öl 4', () => {
  const rules = {
    condition: 'AND',
    rules: [
      {
        id: 'style',
        field: 'style',
        type: 'string',
        input: 'text',
        operator: 'begins_with',
        value: 'Pr 4',
      }
    ],
    not: false,
    valid: true
  };

  const results = doSearch(rules, dbMap.values());

  // Find if Öl 4 is in the results
  const ol4 = results.find(r => r.signature_text === 'Öl 4');

  assert.ok(ol4, 'Should find Öl 4 in results');
  // The style field may contain non-breaking spaces, so we normalize for comparison
  assert.is(ol4.style.replace(/\s/g, ' '), 'Pr 4', 'Öl 4 should have style "Pr 4" (normalized)');

  // Verify we're finding many more results now (not just 3)
  assert.ok(results.length > 100, `Should find many results (found ${results.length})`);
});



// ── stripSpecialSymbols ───────────────────────────────────────────────────────

test('stripSpecialSymbols removes HTML entities &quot; &lt; &gt;', () => {
  assert.is(stripSpecialSymbols('&quot;hello&quot;'), 'hello', 'Should remove &quot; entities');
  assert.is(stripSpecialSymbols('&lt;hello&gt;'), 'hello', 'Should remove &lt; and &gt; entities');
});

test('stripSpecialSymbols removes literal special characters', () => {
  assert.is(stripSpecialSymbols('"text"'), 'text', 'Should remove literal double quotes');
  assert.is(stripSpecialSymbols('[text]'), 'text', 'Should remove square brackets');
  assert.is(stripSpecialSymbols('(text)'), 'text', 'Should remove parentheses');
  assert.is(stripSpecialSymbols('{text}'), 'text', 'Should remove curly braces');
  assert.is(stripSpecialSymbols('a|b'), 'ab', 'Should remove pipe character');
  assert.is(stripSpecialSymbols('a^b'), 'ab', 'Should remove caret');
  assert.is(stripSpecialSymbols('<text>'), 'text', 'Should remove angle brackets');
  assert.is(stripSpecialSymbols('text?'), 'text', 'Should remove question mark');
});

test('stripSpecialSymbols preserves regular text and special Nordic characters', () => {
  assert.is(stripSpecialSymbols('hello'), 'hello', 'Should preserve plain text');
  assert.is(stripSpecialSymbols('Þórr'), 'Þórr', 'Should preserve Nordic characters');
});

// ── getWordSearchFunction – ignoreCase ────────────────────────────────────────

test('getWordSearchFunction exact mode is case-sensitive by default', () => {
  const fn = getWordSearchFunction('exact');
  assert.is(fn('Hello', 'hello'), false, 'Case-sensitive exact match should fail for different cases');
  assert.is(fn('Hello', 'Hello'), true, 'Case-sensitive exact match should succeed for same case');
});

test('getWordSearchFunction exact mode is case-insensitive when ignoreCase=true', () => {
  const fn = getWordSearchFunction('exact', { ignoreCase: true });
  assert.is(fn('Hello', 'hello'), true, 'Case-insensitive exact match should succeed');
  assert.is(fn('HELLO', 'hello'), true, 'Case-insensitive exact match should succeed for all-caps');
});

test('getWordSearchFunction includes mode is case-sensitive by default', () => {
  const fn = getWordSearchFunction('includes');
  assert.is(fn('Hello World', 'hello'), false, 'Case-sensitive includes should fail for different cases');
  assert.is(fn('Hello World', 'Hello'), true, 'Case-sensitive includes should succeed for same case');
});

test('getWordSearchFunction includes mode is case-insensitive when ignoreCase=true', () => {
  const fn = getWordSearchFunction('includes', { ignoreCase: true });
  assert.is(fn('Hello World', 'hello'), true, 'Case-insensitive includes should succeed');
  assert.is(fn('HELLO WORLD', 'hello world'), true, 'Case-insensitive includes should succeed for all-caps');
});

test('getWordSearchFunction beginsWith mode respects ignoreCase', () => {
  const fnSensitive = getWordSearchFunction('beginsWith');
  const fnInsensitive = getWordSearchFunction('beginsWith', { ignoreCase: true });
  assert.is(fnSensitive('Hello', 'hel'), false, 'Case-sensitive beginsWith should fail for different cases');
  assert.is(fnInsensitive('Hello', 'hel'), true, 'Case-insensitive beginsWith should succeed');
});

test('getWordSearchFunction endsWith mode respects ignoreCase', () => {
  const fnSensitive = getWordSearchFunction('endsWith');
  const fnInsensitive = getWordSearchFunction('endsWith', { ignoreCase: true });
  assert.is(fnSensitive('Hello', 'LLO'), false, 'Case-sensitive endsWith should fail for different cases');
  assert.is(fnInsensitive('Hello', 'LLO'), true, 'Case-insensitive endsWith should succeed');
});

// ── getWordSearchFunction – includeSpecialSymbols ─────────────────────────────

test('getWordSearchFunction strips special symbols by default (includeSpecialSymbols=false)', () => {
  const fn = getWordSearchFunction('exact');
  // Word has &quot; markup (personal-name marker); query has no markup.
  // Both sides are stripped before comparison, so they should match.
  assert.is(fn('&quot;Þórr&quot;', 'Þórr'), true, 'Stripped word should match stripped query');
  assert.is(fn('[word]', 'word'), true, 'Literal brackets stripped – should match bare word');
});

test('getWordSearchFunction preserves special symbols when includeSpecialSymbols=true', () => {
  const fn = getWordSearchFunction('exact', { includeSpecialSymbols: true });
  // With symbols kept, "&quot;Þórr&quot;" differs from "Þórr".
  assert.is(fn('&quot;Þórr&quot;', 'Þórr'), false, 'With symbols, annotated word should not match bare query');
  // But an exact query that includes the entities should match.
  assert.is(fn('&quot;Þórr&quot;', '&quot;Þórr&quot;'), true, 'Entity-for-entity query should match');
});

test('getWordSearchFunction includes mode strips symbols by default', () => {
  const fn = getWordSearchFunction('includes');
  assert.is(fn('&quot;Þórr&quot;', 'Þórr'), true, 'includes with stripped symbols should find the word');
});

test('getWordSearchFunction includes mode preserves symbols when includeSpecialSymbols=true', () => {
  const fn = getWordSearchFunction('includes', { includeSpecialSymbols: true });
  // With symbols kept, "[hello]world" does NOT contain "helloworld" as a literal substring.
  // (stripping brackets would make it match; keeping them means it does not)
  assert.is(fn('[hello]world', 'helloworld'), false, 'includes with symbols kept should not match when query is only valid after stripping');
});

test('doSearch does not match all records for symbol-only query when include symbols is off', () => {
  const records = [
    {
      id: 1,
      signature_text: 'T 1',
      normalisation_norse_words: ['foo'],
      normalisation_scandinavian_words: ['foo'],
      transliteration_words: ['foo'],
      normalisation_norse_word_boundaries: [{ start: 0, end: 3, text: 'foo' }],
      normalisation_scandinavian_word_boundaries: [{ start: 0, end: 3, text: 'foo' }],
      transliteration_word_boundaries: [{ start: 0, end: 3, text: 'foo' }],
    },
    {
      id: 2,
      signature_text: 'T 2',
      normalisation_norse_words: ['bar'],
      normalisation_scandinavian_words: ['bar'],
      transliteration_words: ['bar'],
      normalisation_norse_word_boundaries: [{ start: 0, end: 3, text: 'bar' }],
      normalisation_scandinavian_word_boundaries: [{ start: 0, end: 3, text: 'bar' }],
      transliteration_word_boundaries: [{ start: 0, end: 3, text: 'bar' }],
    },
  ];
  const rules = {
    condition: 'AND',
    rules: [{
      id: 'normalization_norse_to_transliteration',
      field: 'normalisation_norse',
      data: { multiField: true },
      operator: 'contains',
      value: { normalization: '?', transliteration: '', names_mode: 'all' },
      includeSpecialSymbols: false,
      ignoreCase: false,
    }],
    valid: true,
  };

  assert.is(doSearch(rules, records).length, 0);
});

// ── doSearch – ignoreCase integration ─────────────────────────────────────────

test('doSearch case-insensitive search finds results regardless of case', () => {
  // The carver field contains "Nilsson" (capital N); searching lowercase should still match.
  const rules = {
    condition: 'AND',
    rules: [
      {
        id: 'carver',
        field: 'carver',
        type: 'string',
        operator: 'contains',
        value: 'nilsson',
        ignoreCase: true,
      }
    ],
    not: false,
    valid: true
  };
  const result = doSearch(rules, dbMap.values());
  assert.ok(result.length > 0, 'Case-insensitive search should find results');
  assert.ok(result.every(r => r.carver.toLowerCase().includes('nilsson')), 'Every result should contain "nilsson" (case-insensitive)');
});

test('doSearch case-sensitive search does not find results with wrong case', () => {
  // "nilsson" (all lowercase) does not appear in the carver field – only "Nilsson" does.
  const rules = {
    condition: 'AND',
    rules: [
      {
        id: 'carver',
        field: 'carver',
        type: 'string',
        operator: 'contains',
        value: 'nilsson',
        ignoreCase: false,
      }
    ],
    not: false,
    valid: true
  };
  const result = doSearch(rules, dbMap.values());
  assert.is(result.length, 0, 'Case-sensitive search should not find results when case does not match');
});

// ── Phrase search in transliteration/normalization ────────────────────────────

/**
 * Build a minimal fake record matching the shape produced by
 * convertDbToKeyMap() for the fields that doWordSearch reads.
 */
function makeWordSearchRecord({
  id,
  norseWords,
  scandinavianWords = null,
  translitWords = null,
}) {
  const tr = translitWords || norseWords;
  const sc = scandinavianWords || norseWords;
  return {
    id,
    signature_text: id,
    normalisation_norse_words: norseWords,
    normalisation_scandinavian_words: sc,
    transliteration_words: tr,
    // word_boundaries are only consulted by highlighting code, not by
    // doWordSearch itself; empty arrays are fine for these tests.
    normalisation_norse_word_boundaries: norseWords.map((text, i) => ({ start: i, end: i + text.length, text })),
    normalisation_scandinavian_word_boundaries: sc.map((text, i) => ({ start: i, end: i + text.length, text })),
    transliteration_word_boundaries: tr.map((text, i) => ({ start: i, end: i + text.length, text })),
    transliteration: tr.join(' '),
  };
}

function buildPhraseRule({
  id = 'normalization_norse_to_transliteration',
  operator,
  normalization = '',
  transliteration = '',
  namesMode = 'includeAll',
  ignoreCase = false,
  includeSpecialSymbols = false,
}) {
  return {
    condition: 'AND',
    rules: [
      {
        id,
        field: id === 'normalization_norse_to_transliteration' ? 'normalisation_norse' : 'normalisation_scandinavian',
        type: 'string',
        operator,
        value: {
          normalization,
          transliteration,
          names_mode: namesMode,
        },
        data: { multiField: true },
        ignoreCase,
        includeSpecialSymbols,
      }
    ],
    not: false,
    valid: true,
  };
}

test('phrase contains: finds record with consecutive matching tokens in normalization', () => {
  const records = [
    makeWordSearchRecord({ id: 'T1', norseWords: ['raised', 'the', 'stone', 'in', 'memory', 'of'] }),
    makeWordSearchRecord({ id: 'T2', norseWords: ['stone', 'of', 'memory'] }),
  ];
  const rules = buildPhraseRule({ operator: 'contains', normalization: 'in memory' });
  const result = doSearch(rules, records);
  assert.is(result.length, 1, 'Only T1 should match the phrase "in memory"');
  assert.is(result[0].id, 'T1');
  assert.equal(result[0].matchDetails.wordIndices, [3, 4], 'Matched word indices span the phrase');
});

test('phrase contains: substring on every token (including middle)', () => {
  const records = [
    makeWordSearchRecord({ id: 'T1', norseWords: ['raised', 'the', 'stone', 'in', 'memory'] }),
  ];
  // Every token is a substring of the corresponding doc word:
  //   'he' ⊂ 'the', 'ton' ⊂ 'stone', 'i' ⊂ 'in'
  const rules = buildPhraseRule({ operator: 'contains', normalization: 'he ton i' });
  const result = doSearch(rules, records);
  assert.is(result.length, 1, 'contains uses substring on every token');
  assert.equal(result[0].matchDetails.wordIndices, [1, 2, 3]);
});

test('phrase contains: partial match allowed on first and last tokens', () => {
  const records = [
    makeWordSearchRecord({ id: 'T1', norseWords: ['raised', 'the', 'stone', 'in', 'memory'] }),
  ];
  // Prefix on last token: "mem" matches "memory"
  const rulesPrefix = buildPhraseRule({ operator: 'contains', normalization: 'in mem' });
  assert.is(doSearch(rulesPrefix, records).length, 1, 'Prefix on last token should match');

  // Suffix on first token: "sed" matches "raised"
  const rulesSuffix = buildPhraseRule({ operator: 'contains', normalization: 'sed the' });
  assert.is(doSearch(rulesSuffix, records).length, 1, 'Suffix on first token should match');
});

test('phrase beginsWith: last token may be a prefix', () => {
  const records = [
    makeWordSearchRecord({ id: 'T1', norseWords: ['raised', 'the', 'stone', 'in', 'memory'] }),
  ];
  const rules = buildPhraseRule({ operator: 'begins_with', normalization: 'in mem' });
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  assert.equal(result[0].matchDetails.wordIndices, [3, 4]);
});

test('phrase endsWith: first token may be a suffix', () => {
  const records = [
    makeWordSearchRecord({ id: 'T1', norseWords: ['raised', 'stone', 'memory', 'of'] }),
  ];
  const rules = buildPhraseRule({ operator: 'ends_with', normalization: 'sed stone' });
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  assert.equal(result[0].matchDetails.wordIndices, [0, 1]);
});

test('phrase search respects ignoreCase flag', () => {
  const records = [
    makeWordSearchRecord({ id: 'T1', norseWords: ['Raised', 'The', 'Stone'] }),
  ];
  const rulesSens = buildPhraseRule({ operator: 'contains', normalization: 'raised the' });
  assert.is(doSearch(rulesSens, records).length, 0, 'Case-sensitive phrase should not match');

  const rulesIns = buildPhraseRule({ operator: 'contains', normalization: 'raised the', ignoreCase: true });
  const result = doSearch(rulesIns, records);
  assert.is(result.length, 1);
  assert.equal(result[0].matchDetails.wordIndices, [0, 1]);
});

test('phrase search namesMode=excludeNames rejects window containing a personal name', () => {
  const records = [
    // A window "Þórr sonr" where Þórr is a personal name marker
    makeWordSearchRecord({ id: 'T1', norseWords: ['raised', '&quot;Þórr&quot;', 'sonr', 'of', 'father'] }),
  ];
  const rules = buildPhraseRule({
    operator: 'contains',
    normalization: 'Þórr sonr',
    namesMode: 'excludeNames',
  });
  assert.is(doSearch(rules, records).length, 0, 'excludeNames should reject window with personal name');

  const rulesAll = buildPhraseRule({ operator: 'contains', normalization: 'Þórr sonr' });
  assert.is(doSearch(rulesAll, records).length, 1, 'Without filter, record should match');
});

test('phrase search namesMode=namesOnly requires at least one personal name in window', () => {
  const recWithName = makeWordSearchRecord({
    id: 'WITH_NAME',
    norseWords: ['raised', '&quot;Þórr&quot;', 'sonr'],
  });
  const recNoName = makeWordSearchRecord({
    id: 'NO_NAME',
    norseWords: ['raised', 'Þórr', 'sonr'],
  });
  const rules = buildPhraseRule({
    operator: 'contains',
    normalization: 'Þórr sonr',
    namesMode: 'namesOnly',
  });
  const result = doSearch(rules, [recWithName, recNoName]);
  assert.is(result.length, 1, 'Only records with a personal name in the window should match');
  assert.is(result[0].id, 'WITH_NAME');
});

test('combined norse+translit phrases must align at the same start index', () => {
  const aligned = makeWordSearchRecord({
    id: 'ALIGNED',
    norseWords: ['raised', 'stone', 'in', 'memory'],
    translitWords: ['raisti', 'stain', 'iR', 'miniR'],
  });
  const misaligned = makeWordSearchRecord({
    id: 'MISALIGNED',
    norseWords: ['raised', 'stone', 'in', 'memory', 'of'],
    translitWords: ['iR', 'miniR', 'raisti', 'stain', 'X'],
  });
  const rules = buildPhraseRule({
    operator: 'contains',
    normalization: 'stone in',
    transliteration: 'stain iR',
  });
  const result = doSearch(rules, [aligned, misaligned]);
  assert.is(result.length, 1, 'Only the record where both phrases start at the same index matches');
  assert.is(result[0].id, 'ALIGNED');
  // Highlighted indices are the union of both windows (same range here)
  assert.equal(result[0].matchDetails.wordIndices, [1, 2]);
});

test('phrase wordIndices are sorted and deduplicated across multiple windows', () => {
  const rec = makeWordSearchRecord({
    id: 'MULTI',
    norseWords: ['a', 'b', 'c', 'a', 'b', 'd'],
  });
  const rules = buildPhraseRule({ operator: 'contains', normalization: 'a b' });
  const result = doSearch(rules, [rec]);
  assert.is(result.length, 1);
  assert.equal(result[0].matchDetails.wordIndices, [0, 1, 3, 4], 'Indices sorted, deduped across windows');
});

test('phrase numPersonalNames is deduplicated across overlapping windows', () => {
  // Build a record where a single personal-name word participates in two
  // overlapping phrase windows. With a 2-token "contains" phrase "a b":
  //   - window [0,1]: 'a' ⊂ 'a', 'b' ⊂ '&quot;a/b&quot;'  → accepted
  //   - window [1,2]: 'a' ⊂ '&quot;a/b&quot;', 'b' ⊂ 'b'  → accepted
  // The personal-name word at index 1 appears in BOTH windows, but must
  // only be counted once in numPersonalNames.
  const rec = makeWordSearchRecord({
    id: 'OVERLAP_NAME',
    norseWords: ['a', '&quot;a/b&quot;', 'b'],
  });
  const rules = buildPhraseRule({ operator: 'contains', normalization: 'a b' });
  const result = doSearch(rules, [rec]);
  assert.is(result.length, 1);
  assert.equal(result[0].matchDetails.wordIndices, [0, 1, 2]);
  assert.is(
    result[0].matchDetails.numPersonalNames,
    1,
    'Personal name shared by overlapping windows is counted once'
  );
});

test('phrase highlight spans a contiguous range via highlightWordsFromWordBoundaries', () => {
  const str = 'raised the stone in memory of';
  const boundaries = [];
  let cursor = 0;
  'raised the stone in memory of'.split(' ').forEach(word => {
    const start = str.indexOf(word, cursor);
    boundaries.push({ start, end: start + word.length, text: word });
    cursor = start + word.length;
  });
  // Simulate a match on "in memory" → indices 3, 4
  const matched = [3, 4];
  const matchedBoundaries = boundaries.filter((_, i) => matched.includes(i));
  const html = highlightWordsFromWordBoundaries(str, matchedBoundaries);
  assert.is(
    html,
    'raised the stone <span class="highlight">in</span> <span class="highlight">memory</span> of',
    'Both matched words are wrapped in highlight spans'
  );
});

test('single-word query still works through the same code path (backwards compat)', () => {
  const rec = makeWordSearchRecord({
    id: 'SINGLE',
    norseWords: ['raised', 'the', 'stone'],
  });
  const rules = buildPhraseRule({ operator: 'contains', normalization: 'stone' });
  const result = doSearch(rules, [rec]);
  assert.is(result.length, 1);
  assert.equal(result[0].matchDetails.wordIndices, [2]);
});

test('symbol-only transliteration query returns transliteration fieldRanges for highlighting', () => {
  const rec = makeWordSearchRecord({
    id: 'SYM_ONLY',
    norseWords: ['alpha', 'beta'],
    translitWords: ['foo', '×', 'bar', '×'],
  });
  rec.transliteration = 'foo × bar ×';

  const rules = buildPhraseRule({
    operator: 'contains',
    transliteration: '×',
    includeSpecialSymbols: true,
  });
  const result = doSearch(rules, [rec]);

  assert.is(result.length, 1, 'Symbol query should match transliteration text');
  assert.equal(
    result[0].matchDetails.fieldRanges.transliteration,
    [[4, 5], [10, 11]],
    'All matching symbol occurrences should be returned as highlight ranges'
  );
});

test('symbol contains with trailing whitespace still highlights terminal symbol occurrence', () => {
  const rec = makeWordSearchRecord({
    id: 'SYM_EDGE',
    norseWords: ['alpha'],
    translitWords: ['foo', '×', 'bar', '×'],
  });
  rec.transliteration = 'foo × bar ×';

  const rules = buildPhraseRule({
    operator: 'contains',
    transliteration: '× ',
    includeSpecialSymbols: true,
  });
  const result = doSearch(rules, [rec]);

  assert.is(result.length, 1, 'Symbol contains-search should still match with trailing whitespace in query');
  assert.equal(
    result[0].matchDetails.fieldRanges.transliteration,
    [[4, 5], [10, 11]],
    'Terminal symbol should be highlighted even when query includes trailing whitespace'
  );
});

test('normalization + symbol transliteration returns both wordIndices and transliteration ranges', () => {
  const rec = makeWordSearchRecord({
    id: 'SYM_COMBINED',
    norseWords: ['stone', 'raised', 'memory'],
    translitWords: ['foo', '×', 'bar'],
  });
  rec.transliteration = 'foo × bar';

  const rules = buildPhraseRule({
    operator: 'contains',
    normalization: 'raised',
    transliteration: '×',
    includeSpecialSymbols: true,
  });
  const result = doSearch(rules, [rec]);

  assert.is(result.length, 1, 'Combined query should match when both parts match');
  assert.equal(result[0].matchDetails.wordIndices, [1], 'Normalization match details are preserved');
  assert.equal(
    result[0].matchDetails.fieldRanges.transliteration,
    [[4, 5]],
    'Transliteration symbol range should be present for rendering'
  );
});

// ── Inscription-level integration tests (Öl 1) ────────────────────────────────
//
// These tests use the real text of Öl 1 (Öland, Sweden) to demonstrate how to
// search a specific inscription by its normalization / transliteration text
// and verify the matched word indices and their character-level boundaries.
//
// Helper: given a plain-text string, split on whitespace runs and return both
// the words and their {start, end, text} character offsets in the original
// string. The main app computes boundaries via getWordBoundaries() over
// HTML-escaped text, but for a search-behavior test this whitespace split is
// sufficient and matches what doWordSearch operates on.
function tokenizeWithBoundaries(text) {
  const words = [];
  const boundaries = [];
  const re = /\S+/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    words.push(m[0]);
    boundaries.push({ start: m.index, end: m.index + m[0].length, text: m[0] });
  }
  return { words, boundaries };
}

// Build an inscription record with the minimum shape doWordSearch reads.
function makeInscriptionFromTexts({ id, norseText, scandinavianText, translitText }) {
  const norse = tokenizeWithBoundaries(norseText);
  const scand = tokenizeWithBoundaries(scandinavianText);
  const trans = tokenizeWithBoundaries(translitText);
  return {
    id,
    signature_text: id,
    normalisation_norse_words: norse.words,
    normalisation_norse_word_boundaries: norse.boundaries,
    normalisation_scandinavian_words: scand.words,
    normalisation_scandinavian_word_boundaries: scand.boundaries,
    transliteration_words: trans.words,
    transliteration_word_boundaries: trans.boundaries,
  };
}

const OL1_NORSE = '§A S[t]e[inn] [þe]ss[i] er settr eptir "Sibba "Góða/"Goða, son "Foldars, en hans liði setti at ... ... Folginn liggr hinns fylgðu, flestr vissi þat, mestar dæðir dolga "Þrúðar draugr í þessu haugi; munat "Reið-Viðurr ráða rógstarkr í "Danmôrku "[E]ndils jôrmungrundar ørgrandari landi. §B {In nomin[e](?) "Ie[su](?) ...}';
const OL1_SCAND = '§A S[t]æ[inn] [sa]s[i] es sattr æftiR "Sibba "Goða/"Guða, sun "Fuldars, en hans liði satti at ... ... Fulginn liggR hinns fylgðu, flæstr vissi þat, mæstaR dæðiR dolga "ÞruðaR draugR i þæimsi haugi; munat "Ræið-Viðurr raða rogstarkR i "Danmarku "[Æ]ndils iarmungrundaR uRgrandaRi landi. §B {In nomin[e](?) "Ie[su](?) ...}';
const OL1_TRANS = '§A + s-a... --(s)- i(a)s · satr · aiftir · si(b)(a) · kuþa · sun · fultars · in hons ·· liþi · sati · at · u · -ausa-þ-... +: fulkin : likr : hins : fulkþu : flaistr (:)· uisi · þat · maistar · taiþir : tulka · þruþar : traukr : i : þaimsi · huki · munat : raiþ:uiþur : raþa : ruk:starkr · i · tanmarku : --ntils : iarmun··kruntar : urkrontari : lonti §B {÷ IN| |NONIN- ¶ + HE... ...}';

test('Öl 1 scandinavian: phrase "es sattr" contains-matches and highlights both words', () => {
  const inscription = makeInscriptionFromTexts({
    id: 'Öl 1',
    norseText: OL1_NORSE,
    scandinavianText: OL1_SCAND,
    translitText: OL1_TRANS,
  });

  const rules = buildPhraseRule({
    id: 'normalization_scandinavian_to_transliteration',
    operator: 'contains',
    normalization: 'es sattr',
  });
  const results = doSearch(rules, [inscription]);

  // Did it match?
  assert.is(results.length, 1, 'Öl 1 should match "es sattr"');

  // Which word indices matched?
  // After whitespace-tokenizing OL1_SCAND, "es" is index 3 and "sattr" is 4.
  assert.equal(results[0].matchDetails.wordIndices, [3, 4]);

  // What are the matched words' character boundaries inside the raw text?
  const matchedBoundaries = results[0].normalisation_scandinavian_word_boundaries
    .filter((_, i) => results[0].matchDetails.wordIndices.includes(i));
  assert.is(matchedBoundaries.length, 2);
  assert.is(matchedBoundaries[0].text, 'es');
  assert.is(matchedBoundaries[1].text, 'sattr');
  // Verify that slicing the raw text with those offsets yields the words.
  assert.is(OL1_SCAND.slice(matchedBoundaries[0].start, matchedBoundaries[0].end), 'es');
  assert.is(OL1_SCAND.slice(matchedBoundaries[1].start, matchedBoundaries[1].end), 'sattr');

  // What the highlighted HTML would look like (main-page rendering path).
  const html = highlightWordsFromWordBoundaries(OL1_SCAND, matchedBoundaries);
  assert.ok(
    html.includes('<span class="highlight">es</span> <span class="highlight">sattr</span>'),
    'Highlight should wrap both matched words contiguously'
  );
});

test('Öl 1 scandinavian: phrase "es satt" contains-matches (last token prefix of "sattr")', () => {
  const inscription = makeInscriptionFromTexts({
    id: 'Öl 1',
    norseText: OL1_NORSE,
    scandinavianText: OL1_SCAND,
    translitText: OL1_TRANS,
  });

  const rules = buildPhraseRule({
    id: 'normalization_scandinavian_to_transliteration',
    operator: 'contains',
    normalization: 'es satt',
  });
  const results = doSearch(rules, [inscription]);

  // Phrase contains allows a prefix on the last token, the same way that
  // single-word contains "sat" matches "sattr". So "es satt" matches
  // "es sattr" at word indices [3, 4].
  assert.is(results.length, 1, 'Öl 1 should match "es satt" under contains');
  assert.equal(results[0].matchDetails.wordIndices, [3, 4]);

  const matchedBoundaries = results[0].normalisation_scandinavian_word_boundaries
    .filter((_, i) => results[0].matchDetails.wordIndices.includes(i));
  assert.is(matchedBoundaries[0].text, 'es');
  assert.is(matchedBoundaries[1].text, 'sattr',
    'The whole matched word "sattr" is highlighted, not just the partial query "satt"');
});

test('Öl 1 scandinavian: phrase "es satt" does NOT equal-match (equal requires exact tokens)', () => {
  const inscription = makeInscriptionFromTexts({
    id: 'Öl 1',
    norseText: OL1_NORSE,
    scandinavianText: OL1_SCAND,
    translitText: OL1_TRANS,
  });

  const rules = buildPhraseRule({
    id: 'normalization_scandinavian_to_transliteration',
    operator: 'equal',
    normalization: 'es satt',
  });
  const results = doSearch(rules, [inscription]);

  // equal requires strict token equality. "satt" != "sattr", so no match.
  assert.is(results.length, 0, 'equal requires strict token equality');
});

test('Öl 1 scandinavian: phrase "es sattr" equal-matches (strict tokens)', () => {
  const inscription = makeInscriptionFromTexts({
    id: 'Öl 1',
    norseText: OL1_NORSE,
    scandinavianText: OL1_SCAND,
    translitText: OL1_TRANS,
  });

  const rules = buildPhraseRule({
    id: 'normalization_scandinavian_to_transliteration',
    operator: 'equal',
    normalization: 'es sattr',
  });
  const results = doSearch(rules, [inscription]);

  assert.is(results.length, 1);
  assert.equal(results[0].matchDetails.wordIndices, [3, 4]);
});

test('Öl 1 scandinavian: phrase "es satt" begins_with-matches (last token may be a prefix)', () => {
  const inscription = makeInscriptionFromTexts({
    id: 'Öl 1',
    norseText: OL1_NORSE,
    scandinavianText: OL1_SCAND,
    translitText: OL1_TRANS,
  });

  const rules = buildPhraseRule({
    id: 'normalization_scandinavian_to_transliteration',
    operator: 'begins_with',
    normalization: 'es satt',
  });
  const results = doSearch(rules, [inscription]);

  // begins_with phrase semantics: tokens 0..N-2 must equal doc words exactly,
  // and the last doc word must start with the last token. "sattr" starts with
  // "satt", so the window [3, 4] matches.
  assert.is(results.length, 1, 'Öl 1 should match "es satt" under begins_with');
  assert.equal(results[0].matchDetails.wordIndices, [3, 4]);

  const matchedBoundaries = results[0].normalisation_scandinavian_word_boundaries
    .filter((_, i) => results[0].matchDetails.wordIndices.includes(i));
  assert.is(matchedBoundaries[0].text, 'es');
  assert.is(matchedBoundaries[1].text, 'sattr',
    'Even though query is "satt", the whole matched word "sattr" is highlighted');
});

// ---------------------------------------------------------------------------
// Tests for translation custom search functions (via doSearch)
// ---------------------------------------------------------------------------

function makeTranslationRecord({ id, english = '', swedish = '' }) {
  return {
    id,
    signature_text: id,
    english_translation: english,
    swedish_translation: swedish,
  };
}

function buildTranslationRule({ id, operator, value, ignoreCase = false }) {
  return {
    condition: 'AND',
    rules: [
      {
        id,
        field: id,
        type: 'string',
        operator,
        value,
        ignoreCase,
      }
    ],
    not: false,
    valid: true,
  };
}

test('translation contains: finds a single occurrence and records its range', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'Bjorn raised this stone' }),
    makeTranslationRecord({ id: 'T2', english: 'No match here' }),
  ];
  const rules = buildTranslationRule({ id: 'english_translation', operator: 'contains', value: 'stone' });
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  assert.is(result[0].id, 'T1');
  const ranges = result[0].matchDetails.fieldRanges.english_translation;
  assert.equal(ranges, [[18, 23]]);
  assert.is(result[0].english_translation.slice(18, 23), 'stone');
});

test('translation contains: records all non-overlapping occurrences', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'stone and another stone' }),
  ];
  const rules = buildTranslationRule({ id: 'english_translation', operator: 'contains', value: 'stone' });
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  const ranges = result[0].matchDetails.fieldRanges.english_translation;
  assert.equal(ranges, [[0, 5], [18, 23]]);
});

test('translation contains: ignoreCase=true matches different case', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'Stone and STONE' }),
  ];
  const rules = buildTranslationRule({
    id: 'english_translation',
    operator: 'contains',
    value: 'stone',
    ignoreCase: true,
  });
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  const ranges = result[0].matchDetails.fieldRanges.english_translation;
  assert.equal(ranges, [[0, 5], [10, 15]]);
  // Highlighted slices preserve original casing.
  assert.is(result[0].english_translation.slice(0, 5), 'Stone');
  assert.is(result[0].english_translation.slice(10, 15), 'STONE');
});

test('translation contains: ignoreCase=false is case-sensitive', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'Stone' }),
  ];
  const rules = buildTranslationRule({
    id: 'english_translation',
    operator: 'contains',
    value: 'stone',
    ignoreCase: false,
  });
  const result = doSearch(rules, records);
  assert.is(result.length, 0);
});

test('translation begins_with: matches prefix and highlights only the prefix', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'Bjorn raised this stone' }),
    makeTranslationRecord({ id: 'T2', english: 'After Bjorn' }),
  ];
  const rules = buildTranslationRule({ id: 'english_translation', operator: 'begins_with', value: 'Bjorn' });
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  assert.is(result[0].id, 'T1');
  assert.equal(result[0].matchDetails.fieldRanges.english_translation, [[0, 5]]);
});

test('translation ends_with: matches suffix and highlights only the suffix', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'raised this stone' }),
  ];
  const rules = buildTranslationRule({ id: 'english_translation', operator: 'ends_with', value: 'stone' });
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  const ranges = result[0].matchDetails.fieldRanges.english_translation;
  assert.equal(ranges, [[12, 17]]);
});

test('translation equal: matches exact value and highlights whole string', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'stone' }),
    makeTranslationRecord({ id: 'T2', english: 'stone.' }),
  ];
  const rules = buildTranslationRule({ id: 'english_translation', operator: 'equal', value: 'stone' });
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  assert.is(result[0].id, 'T1');
  assert.equal(result[0].matchDetails.fieldRanges.english_translation, [[0, 5]]);
});

test('translation equal: ignoreCase works', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'Stone' }),
  ];
  const rules = buildTranslationRule({
    id: 'english_translation',
    operator: 'equal',
    value: 'stone',
    ignoreCase: true,
  });
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  assert.equal(result[0].matchDetails.fieldRanges.english_translation, [[0, 5]]);
});

test('swedish_translation contains uses its own fieldRanges key', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', swedish: 'Björn reste denna sten' }),
  ];
  const rules = buildTranslationRule({ id: 'swedish_translation', operator: 'contains', value: 'sten' });
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  assert.ok(result[0].matchDetails.fieldRanges.swedish_translation);
  assert.not.ok(result[0].matchDetails.fieldRanges.english_translation);
});

test('translation contains: empty ruleValue produces no match', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'anything' }),
  ];
  const rules = buildTranslationRule({ id: 'english_translation', operator: 'contains', value: '' });
  const result = doSearch(rules, records);
  assert.is(result.length, 0);
});

test('translation AND-merge: translation contains + translation contains on same field unions ranges', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'stone and hammer' }),
  ];
  const rules = {
    condition: 'AND',
    rules: [
      {
        id: 'english_translation', field: 'english_translation', type: 'string',
        operator: 'contains', value: 'stone', ignoreCase: false,
      },
      {
        id: 'english_translation', field: 'english_translation', type: 'string',
        operator: 'contains', value: 'hammer', ignoreCase: false,
      },
    ],
    not: false,
    valid: true,
  };
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  const ranges = result[0].matchDetails.fieldRanges.english_translation;
  // Both ranges should be present (order is insertion order per field).
  assert.equal(
    ranges.slice().sort((a, b) => a[0] - b[0]),
    [[0, 5], [10, 16]]
  );
});

test('translation AND-merge: duplicate ranges are deduped', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'stone' }),
  ];
  // Two identical translation rules produce the same [0,5] range.
  const rules = {
    condition: 'AND',
    rules: [
      {
        id: 'english_translation', field: 'english_translation', type: 'string',
        operator: 'contains', value: 'stone', ignoreCase: false,
      },
      {
        id: 'english_translation', field: 'english_translation', type: 'string',
        operator: 'contains', value: 'stone', ignoreCase: false,
      },
    ],
    not: false,
    valid: true,
  };
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  assert.equal(result[0].matchDetails.fieldRanges.english_translation, [[0, 5]]);
});

test('translation search does not produce wordIndices', () => {
  const records = [
    makeTranslationRecord({ id: 'T1', english: 'a stone' }),
  ];
  const rules = buildTranslationRule({ id: 'english_translation', operator: 'contains', value: 'stone' });
  const result = doSearch(rules, records);
  assert.is(result.length, 1);
  assert.not.ok(result[0].matchDetails.wordIndices);
});

test.run();
