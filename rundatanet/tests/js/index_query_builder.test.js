import './setup-mocks.js';

import { test } from 'uvu';
import * as assert from 'uvu/assert';
import { convertDbToKeyMap } from '../../runes/js/index_scripts.js';
import { mockDb } from './mockDb.js';

// Now import the module
import {
  applyLiveQueryBuilderValuesToRules,
  getValuesFromAllData,
  normalizeQueryBuilderRulesForUi,
  sortGroupsByOrder,
} from '../../runes/js/index_query_builder.js';
import {
  formatCountryProvinceRuleValue,
  getCountryProvinceSuggestions,
} from '../../runes/js/index_country_province.js';

test('sortGroupsByOrder() with specified order', () => {
  const items = [
    { id: 1, label: 'B Item', optgroup: 'group2' },
    { id: 2, label: 'A Item', optgroup: 'group1' },
    { id: 4, label: 'D Item', optgroup: 'group1' },
    { id: 3, label: 'C Item', optgroup: 'group3' },
  ];

  const groupOrder = ['group1', 'group2', 'group3'];
  const result = sortGroupsByOrder(items, groupOrder);

  // Check groups are in correct order
  assert.is(result[0].optgroup, 'group1', 'First group should be group1');
  assert.is(result[1].optgroup, 'group1', 'Second item should also be group1');
  assert.is(result[2].optgroup, 'group2', 'Third item should be group2');
  assert.is(result[3].optgroup, 'group3', 'Fourth item should be group3');

  // Check alphabetical sorting within groups
  assert.is(result[0].label, 'A Item', 'Items within group1 should be alphabetically sorted');
  assert.is(result[1].label, 'D Item', 'Items within group1 should be alphabetically sorted');
});

test('sortGroupsByOrder() with unspecified groups', () => {
  const items = [
    { id: 1, label: 'A Item', optgroup: 'group1' },
    { id: 2, label: 'B Item', optgroup: 'group2' },
    { id: 3, label: 'C Item', optgroup: 'unspecified1' },
    { id: 4, label: 'D Item', optgroup: 'unspecified2' }
  ];

  const groupOrder = ['group1', 'group2'];
  const result = sortGroupsByOrder(items, groupOrder);

  // Specified groups should come first in the correct order
  assert.is(result[0].optgroup, 'group1', 'First group should be group1');
  assert.is(result[1].optgroup, 'group2', 'Second group should be group2');

  // Unspecified groups should be included at the end
  assert.ok(
    (result[2].optgroup === 'unspecified1' && result[3].optgroup === 'unspecified2') ||
    (result[2].optgroup === 'unspecified2' && result[3].optgroup === 'unspecified1'),
    'Unspecified groups should be included at the end'
  );
});

test('normalizeQueryBuilderRulesForUi() converts legacy inscription ID list rules', () => {
  const rules = {
    condition: 'AND',
    rules: [
      {
        id: 'inscription_id',
        field: 'signature_text',
        operator: 'in',
        value: ['Öl 1', 'Sö Fv1986;218'],
      },
      {
        id: 'inscription_country',
        field: 'signature_text',
        operator: 'in',
        value: ['Öl '],
      },
      {
        id: 'inscription_id',
        field: 'signature_text',
        operator: 'in_separated_list',
        value: 'Öl 2, Öl 3',
      },
    ],
    not: false,
  };

  const result = normalizeQueryBuilderRulesForUi(rules);

  assert.is(result.rules[0].operator, 'equal');
  assert.is(result.rules[0].value, 'Öl 1|Sö Fv1986;218');
  assert.is(result.rules[1].operator, 'in');
  assert.is(result.rules[2].operator, 'equal');
  assert.is(result.rules[2].value, 'Öl 2, Öl 3');
  assert.ok(result !== rules, 'Should return a copy of the root object');
});

test('normalizeQueryBuilderRulesForUi() expands legacy broad runic text rules', () => {
  const rules = {
    condition: 'AND',
    rules: [
      {
        id: 'search_runic_texts',
        field: 'normalisation_norse',
        type: 'string',
        operator: 'contains',
        value: 'stein',
        data: { multiField: true },
        ignoreCase: true,
        includeSpecialSymbols: false,
      },
    ],
    not: false,
  };

  const result = normalizeQueryBuilderRulesForUi(rules);
  const expanded = result.rules[0];

  assert.is(expanded.condition, 'OR');
  assert.is(expanded.rules.length, 5);
  assert.equal(
    expanded.rules.map(rule => rule.id),
    [
      'normalization_norse_to_transliteration',
      'normalization_scandinavian_to_transliteration',
      'normalization_norse_to_transliteration',
      'english_translation',
      'swedish_translation',
    ]
  );
  assert.is(expanded.rules[0].value.normalization, 'stein');
  assert.is(expanded.rules[1].value.normalization, 'stein');
  assert.is(expanded.rules[2].value.transliteration, 'stein');
  assert.is(expanded.rules[3].value, 'stein');
  assert.is(expanded.rules[4].value, 'stein');
  assert.is(expanded.rules[0].ignoreCase, true);
  assert.is(expanded.rules[0].includeSpecialSymbols, false);
});

test('applyLiveQueryBuilderValuesToRules() copies visible ID and country text into rules', () => {
  const originalDollar = global.$;
  const liveRules = [
    { filter: 'inscription_id', value: 'Öl 1, Sö Fv1986;218' },
    { filter: 'inscription_country', value: 'Öland, Denmark' },
  ];

  global.$ = function(selectorOrElement) {
    if (selectorOrElement === '#builder .rule-container') {
      return {
        each(callback) {
          liveRules.forEach((rule, index) => callback.call(rule, index, rule));
        },
      };
    }

    if (selectorOrElement && typeof selectorOrElement === 'object') {
      return {
        find(selector) {
          if (selector.includes('.rule-filter-container')) {
            return { val: () => selectorOrElement.filter };
          }
          if (selector.includes('.rule-value-container')) {
            return { val: () => selectorOrElement.value };
          }
          return { val: () => '' };
        },
      };
    }

    return originalDollar(selectorOrElement);
  };

  try {
    const rules = {
      condition: 'AND',
      rules: [
        {
          id: 'inscription_id',
          field: 'signature_text',
          operator: 'equal',
          value: '',
        },
        {
          id: 'inscription_country',
          field: 'signature_text',
          operator: 'in',
          value: '',
        },
      ],
    };

    const result = applyLiveQueryBuilderValuesToRules(rules, 'builder');
    assert.is(result.rules[0].value, 'Öl 1, Sö Fv1986;218');
    assert.is(result.rules[1].value, 'Öland, Denmark');
  } finally {
    global.$ = originalDollar;
  }
});

test('country/province helpers format saved values and suggest typed options', () => {
  assert.is(formatCountryProvinceRuleValue(['Öl ', 'DR ']), 'Öland (Öl), Denmark (DR)');

  const denmarkSuggestions = getCountryProvinceSuggestions('Öland, Den');
  assert.is(denmarkSuggestions[0], 'Öland, Denmark (DR)');
  assert.ok(denmarkSuggestions.includes('Öland, Denmark (DR)'));

  const diacriticFreeSuggestions = getCountryProvinceSuggestions('Oland');
  assert.ok(diacriticFreeSuggestions.includes('Öland (Öl)'));
});

test('sortGroupsByOrder() with items without optgroup', () => {
  const items = [
    { id: 1, label: 'B Item', optgroup: 'group1' },
    { id: 2, label: 'A Item', optgroup: '' },
    { id: 3, label: 'C Item' }
  ];

  const groupOrder = ['group1'];
  const result = sortGroupsByOrder(items, groupOrder);

  assert.is(result[0].optgroup, 'group1', 'Items with specified optgroup should come first');
  assert.is(result[1].label, 'A Item', 'Items without optgroup should be included');
  assert.is(result[2].label, 'C Item', 'Items without optgroup property should be included');
});

test('sortGroupsByOrder() with empty arrays', () => {
  // Test with empty items array
  const result1 = sortGroupsByOrder([], ['group1', 'group2']);
  assert.is(result1.length, 0, 'Empty items array should return empty array');

  // Test with empty groupOrder array
  const items = [
    { id: 1, label: 'B Item', optgroup: 'group1' },
    { id: 2, label: 'A Item', optgroup: 'group1' },
    { id: 3, label: 'E Item', optgroup: 'group2' },
    { id: 4, label: 'Z Item', optgroup: 'group2' }
  ];

  const result2 = sortGroupsByOrder(items, []);
  assert.is(result2.length, 4, 'All items should be included with empty groupOrder');

  // Items should still be sorted alphabetically within their groups
  const group1Items = result2.filter(item => item.optgroup === 'group1');
  const group2Items = result2.filter(item => item.optgroup === 'group2');

  assert.is(group1Items.length, 2, 'Group1 items should be present');
  assert.is(group2Items.length, 2, 'Group2 items should be present');
});

//  const result = convertDbToKeyMap(mockDb);

// Helper function to simulate the 'suggest' callback
function createSuggestMock() {
  const suggested = [];
  return {
    callback: (values) => {
      suggested.push(...(Array.isArray(values) ? values : [values]));
    },
    suggested
  };
}

test('getValuesFromAllData() with empty term and aliases', () => {
  const mockDbMap = new Map([
    [1, {
      id: 1,
      testField: 'Alpha',
      aliases: 'AlphaAlias1|AlphaAlias2'
    }],
    [2, {
      id: 2,
      testField: 'Bravo',
      aliases: 'BravoAlias'
    }],
    [3, {
      id: 3,
      testField: 'Charlie',
      aliases: ''
    }],
    [4, {
      id: 4,
      testField: 'Delta',
      aliases: ''
    }],
    [5, {
      id: 5,
      testField: 'Åkerman',
      aliases: ''
    }],
    [6, {
      id: 6,
      testField: '',
      aliases: ''
    }],
  ]);
  const { callback, suggested } = createSuggestMock();

  // Act
  getValuesFromAllData('', callback, 'testField', mockDbMap);

  // Assert
  assert.is(suggested.length, 5, 'Should return 5 values (all non-empty)');
  assert.ok(suggested.includes('Alpha'), 'Should include Alpha');
  assert.ok(suggested.includes('Bravo'), 'Should include Bravo');
  assert.ok(suggested.includes('Charlie'), 'Should include Charlie');
  assert.ok(suggested.includes('Delta'), 'Should include Delta');
  assert.ok(suggested.includes('Åkerman'), 'Should include Åkerman');
});

test('getValuesFromAllData() with signature_text', () => {
  const mockDbMap = new Map([
    [1, {
      id: 1,
      signature_text: 'Alpha',
      aliases: 'AlphaAlias1|AlphaAlias2'
    }],
    [2, {
      id: 2,
      signature_text: 'Bravo',
      aliases: 'BravoAlias'
    }],
    [3, {
      id: 3,
      signature_text: 'Charlie',
      aliases: ''
    }],
    [4, {
      id: 4,
      signature_text: 'Delta',
      aliases: ''
    }],
    [5, {
      id: 5,
      signature_text: 'Åkerman',
      aliases: ''
    }],
    [6, {
      id: 6,
      signature_text: '',
      aliases: ''
    }],
  ]);
  const { callback, suggested } = createSuggestMock();

  // Act
  getValuesFromAllData('', callback, 'signature_text', mockDbMap);

  // Assert
  assert.is(suggested.length, 8, 'Should return 8 values (5 non-empty + 3 aliases)');
});

test('sortGroupsByOrder() maintains group order for sorted input', () => {
  // This test verifies that filters already sorted by optGroups order remain in correct order
  const optGroupsOrder = ['gr_inscription', 'gr_texts', 'gr_location', 'gr_time_period', 'gr_design', 'gr_more_info'];

  const items = [
    { id: 'inscription_id', label: 'Inscription ID', optgroup: 'gr_inscription' },
    { id: 'normalization', label: 'Normalization', optgroup: 'gr_texts' },
    { id: 'translation', label: 'Translation', optgroup: 'gr_texts' },
    { id: 'country', label: 'Country', optgroup: 'gr_location' },
    { id: 'parish', label: 'Parish', optgroup: 'gr_location' },
    { id: 'dating', label: 'Dating', optgroup: 'gr_time_period' },
    { id: 'year_from', label: 'Year From', optgroup: 'gr_time_period' },
    { id: 'carver', label: 'Carver', optgroup: 'gr_design' },
    { id: 'material', label: 'Material', optgroup: 'gr_design' },
    { id: 'reference', label: 'Reference', optgroup: 'gr_more_info' },
  ];

  const result = sortGroupsByOrder(items, optGroupsOrder);

  // Verify the groups appear in the correct order
  let currentGroupIndex = -1;
  let lastGroup = '';

  for (const item of result) {
    const groupIndex = optGroupsOrder.indexOf(item.optgroup);

    // Group index should never decrease (groups should stay in order)
    assert.ok(groupIndex >= currentGroupIndex,
      `Group ${item.optgroup} (index ${groupIndex}) should not appear before ${lastGroup} (index ${currentGroupIndex})`);

    if (groupIndex > currentGroupIndex) {
      currentGroupIndex = groupIndex;
      lastGroup = item.optgroup;
    }
  }

  // Verify all groups are present
  const resultGroups = [...new Set(result.map(item => item.optgroup))];
  assert.is(resultGroups.length, 6, 'All 6 groups should be present');

  // Verify the first item is from gr_inscription
  assert.is(result[0].optgroup, 'gr_inscription', 'First item should be from gr_inscription');

  // Verify the last item is from gr_more_info
  assert.is(result[result.length - 1].optgroup, 'gr_more_info', 'Last item should be from gr_more_info');
});

test('getRules output with function-valued input survives structuredClone after JSON round-trip', () => {
  // Simulate what QueryBuilder's getRules() returns for custom filters like
  // createWordSearchRule — where `input` is a function, not a string.
  const rulesWithFunctions = {
    condition: 'AND',
    valid: true,
    rules: [
      {
        id: 'normalization_norse_to_transliteration',
        field: 'normalization_norse',
        type: 'string',
        input: function(rule, name) { return '<div>custom HTML</div>'; },
        operator: 'contains',
        value: { normalization: 'test', transliteration: '', names_mode: 'includeAll' },
        data: { multiField: true },
      },
      {
        id: 'transliteration',
        field: 'transliteration',
        type: 'string',
        input: 'text',
        operator: 'contains',
        value: 'abc',
      }
    ]
  };

  // Raw rules with functions should fail structuredClone (= postMessage)
  assert.throws(
    () => structuredClone(rulesWithFunctions),
    'Raw rules with function input should fail structuredClone'
  );

  // JSON round-trip strips functions, making the object safe for postMessage
  const cloneable = JSON.parse(JSON.stringify(rulesWithFunctions));
  assert.not.throws(
    () => structuredClone(cloneable),
    'Cleaned rules should pass structuredClone'
  );

  // Verify data integrity is preserved
  assert.is(cloneable.condition, 'AND');
  assert.is(cloneable.valid, true);
  assert.is(cloneable.rules[0].id, 'normalization_norse_to_transliteration');
  assert.is(cloneable.rules[0].operator, 'contains');
  assert.is(cloneable.rules[0].value.normalization, 'test');
  assert.is(cloneable.rules[0].data.multiField, true);
  assert.is(cloneable.rules[1].input, 'text', 'String-valued input should be preserved');
  assert.type(cloneable.rules[0].input, 'undefined', 'Function-valued input should be stripped');
});

test.run();
