import { isCompactDbLayout } from './index_layout.js';
import {
  formatCountryProvinceRuleValue,
  getCountryProvinceSuggestions,
} from './index_country_province.js';

/*
This file contains code to work with jquery query builder. The query builder must be
included in your code prior to using this file.
*/


const queryBuilderPlugins = {
  'bt-tooltip-errors': null,
  'sortable': null,
  'not-group': null,
  'case-rule': null,
  'special-symbols-rule': null,
};

const optGroups = {
  "gr_inscription": {
    "en": "Inscription",
    "sv": "Signatura",
  },
  "gr_texts": "Texts",
  "gr_location": "Location",
  "gr_time_period": "Time Period",
  "gr_design": "Design",
  "gr_more_info": "More information",
};

function ensureTextOptionsRow(rule) {
  const $container = rule.$el.find('.rule-value-container');
  let $row = $container.find('[data-text-options-row=rule]').first();
  if ($row.length > 0) {
    return $row;
  }

  const $personalModeInput = $container.find('[name$=_personalNamesMode]').first();
  if ($personalModeInput.length > 0) {
    $row = $personalModeInput.closest('.mt-2');
    $row.attr('data-text-options-row', 'rule');
    return $row;
  }

  $row = $('<div class="mt-2" data-text-options-row="rule"></div>');
  $container.append($row);
  return $row;
}

// QueryBuilder plugin for case-(in)sensitive search
$.fn.queryBuilder.define('case-rule', function(options) {
  let self = this;

  // Bind events
  this.on('afterInit', function() {
    self.$el.on('change.queryBuilder', '[data-case=rule]', function () {
      let $rule = $(this).closest($.fn.queryBuilder.constructor.selectors.rule_container);
      let rule = self.getModel($rule);
      // Checked "match case" means case-sensitive search.
      rule.ignoreCase = !$(this).is(':checked');
    });

    self.model.on('update', function(e, node, field) {
      if (node instanceof $.fn.queryBuilder.constructor.Rule && field === 'ignoreCase') {
        self.updateRuleCaseIgnore(node);
      }
    });
  });

  // Init case-sensitivity property
  this.on('afterAddRule', function(e, rule) {
    // Default behavior requested: ignore case.
    rule.__.ignoreCase = true;
  });

  this.on('afterCreateRuleInput.filter', function(e, rule) {
    // Show plugin's button only for normalization, transliteration and translation filters
    const caseRuleFilterIds = [
      'normalization_norse_to_transliteration',
      'normalization_scandinavian_to_transliteration',
      'search_runic_texts',
      'english_translation',
      'swedish_translation',
    ];
    const shouldShow = rule.filter && caseRuleFilterIds.includes(rule.filter.id);
    const $row = ensureTextOptionsRow(rule);
    if ($row.find(cssSelectorPluginCaseRule).length === 0) {
      $row.append(
        `<div class="form-check form-check-inline" data-case-container="rule">
          <input class="form-check-input" type="checkbox" data-case="rule" id="${rule.id}_matchCaseInput">
          <label class="form-check-label" for="${rule.id}_matchCaseInput">Match case</label>
        </div>`
      );
    }

    if (shouldShow) {
      $row.find(cssSelectorPluginCaseRule).show();
      self.updateRuleCaseIgnore(rule);
    } else {
      $row.find(cssSelectorPluginCaseRule).hide();
    }
  });

  // Export "case-rule" to JSON
  this.on('ruleToJson.filter', function(e, rule) {
    e.value.ignoreCase = rule.ignoreCase;
  });

  // Read "case-rule" from JSON
  this.on('jsonToRule.filter', function(e, json) {
    e.value.ignoreCase = !!json.ignoreCase;
  });

  // Export case selector to SQL
  this.on('ruleToSQL.filter', function(e, rule, value, sqlFn) {
    console.log(`ruleToSQL.filter: ${rule.id}, ignoreCase: ${rule.ignoreCase}`);
    if (rule.ignoreCase) {
      e.value = 'NOCASE ( ' + e.value + ' )';
    }
  });
}, {
  disable_template: true
});

$.fn.queryBuilder.constructor.utils.defineModelProperties($.fn.queryBuilder.constructor.Rule, ['ignoreCase']);

const cssSelectorPluginCaseRule = '[data-case-container=rule]';
const cssSelectorPluginCaseRuleInput = cssSelectorPluginCaseRule + ' [data-case=rule]';

$.fn.queryBuilder.extend({
  /**
   * Performs actions when a rule's case selector changes
   * @param {Rule} rule
   * @fires module:plugins.CaseSelector.updateRuleCaseIgnore
   * @private
   */
  updateRuleCaseIgnore: function(rule) {
      rule.$el.find(cssSelectorPluginCaseRuleInput).prop('checked', !rule.ignoreCase);

      /**
       * After the rule's case selector has been modified
       * @event afterUpdateRuleCaseSelector
       * @memberof module:plugins.CaseSelector
       * @param {Rule} rule
       */
      this.trigger('afterUpdateRuleCaseSelector', rule);

      this.trigger('rulesChanged');
  }
});

// QueryBuilder plugin for including/excluding special editorial symbols in search
// Applies to normalisation and transliteration filters only.
// When includeSpecialSymbols is false (default), the search engine strips editorial
// symbols (e.g. " [ ] ( ) { } | ^ ´ < > ?) from both the data words and the query
// before comparing, making symbols invisible to the search.
// When true, symbols are included as-is in the comparison.
const specialSymbolsFilterIds = [
  'normalization_norse_to_transliteration',
  'normalization_scandinavian_to_transliteration',
  'search_runic_texts',
];

$.fn.queryBuilder.define('special-symbols-rule', function(options) {
  let self = this;

  this.on('afterInit', function() {
    self.$el.on('change.queryBuilder', '[data-special-symbols=rule]', function() {
      let $rule = $(this).closest($.fn.queryBuilder.constructor.selectors.rule_container);
      let rule = self.getModel($rule);
      rule.includeSpecialSymbols = $(this).is(':checked');
    });

    self.model.on('update', function(e, node, field) {
      if (node instanceof $.fn.queryBuilder.constructor.Rule && field === 'includeSpecialSymbols') {
        self.updateRuleSpecialSymbols(node);
      }
    });
  });

  // Default: strip special symbols (includeSpecialSymbols = false)
  this.on('afterAddRule', function(e, rule) {
    rule.__.includeSpecialSymbols = false;
  });

  this.on('afterCreateRuleInput.filter', function(e, rule) {
    const shouldShow = rule.filter && specialSymbolsFilterIds.includes(rule.filter.id);
    const $row = ensureTextOptionsRow(rule);
    if ($row.find(cssSelectorPluginSpecialSymbolsRule).length === 0) {
      $row.append(
        `<div class="form-check form-check-inline" data-special-symbols-container="rule">
          <input class="form-check-input" type="checkbox" data-special-symbols="rule" id="${rule.id}_includeSymbolsInput">
          <label class="form-check-label" for="${rule.id}_includeSymbolsInput">Include symbols</label>
        </div>`
      );
    }

    if (shouldShow) {
      $row.find(cssSelectorPluginSpecialSymbolsRule).show();
      self.updateRuleSpecialSymbols(rule);
    } else {
      $row.find(cssSelectorPluginSpecialSymbolsRule).hide();
    }
  });

  this.on('ruleToJson.filter', function(e, rule) {
    e.value.includeSpecialSymbols = rule.includeSpecialSymbols;
  });

  this.on('jsonToRule.filter', function(e, json) {
    e.value.includeSpecialSymbols = !!json.includeSpecialSymbols;
  });
}, {
  disable_template: true
});

$.fn.queryBuilder.constructor.utils.defineModelProperties($.fn.queryBuilder.constructor.Rule, ['includeSpecialSymbols']);

const cssSelectorPluginSpecialSymbolsRule = '[data-special-symbols-container=rule]';
const cssSelectorPluginSpecialSymbolsRuleInput = cssSelectorPluginSpecialSymbolsRule + ' [data-special-symbols=rule]';

$.fn.queryBuilder.extend({
  updateRuleSpecialSymbols: function(rule) {
    rule.$el.find(cssSelectorPluginSpecialSymbolsRuleInput).prop('checked', !!rule.includeSpecialSymbols);
    this.trigger('rulesChanged');
  }
});


export function sortGroupsByOrder(items, groupOrder) {
  const key = 'optgroup'; // The key in items to group by

  // Create priority map
  const priorityMap = {};
  groupOrder.forEach((group, index) => {
    priorityMap[group] = index;
  });

  // Group items by their key
  const groups = {};
  items.forEach(item => {
    const groupKey = item[key] || '';
    if (!groups[groupKey]) groups[groupKey] = [];
    groups[groupKey].push(item);
  });

  // Sort each group alphabetically by label
  Object.keys(groups).forEach(groupKey => {
    groups[groupKey].sort((a, b) => {
      const labelA = a.label || '';
      const labelB = b.label || '';
      return labelA.localeCompare(labelB);
    });
  });

  // Create result array by concatenating groups in specified order
  let result = [];
  groupOrder.forEach(groupKey => {
    if (groups[groupKey]) {
      result = result.concat(groups[groupKey]);
      delete groups[groupKey];
    }
  });

  // Add any remaining groups not specified in groupOrder
  Object.values(groups).forEach(group => {
    result = result.concat(group);
  });

  return result;
}

export function normalizeQueryBuilderRulesForUi(rules) {
  if (!rules || typeof rules !== 'object') {
    return rules;
  }

  const normalized = Array.isArray(rules) ? rules.slice() : { ...rules };
  if (Array.isArray(normalized.rules)) {
    normalized.rules = normalized.rules.map(rule => normalizeQueryBuilderRulesForUi(rule));
  }

  if (
    normalized.id === 'inscription_id'
    && (normalized.operator === 'in' || normalized.operator === 'in_separated_list')
  ) {
    normalized.operator = 'equal';
    if (Array.isArray(normalized.value)) {
      normalized.value = normalized.value.join('|');
    }
  }

  return normalized;
}

export function applyLiveQueryBuilderValuesToRules(rules, containerId = 'builder') {
  if (!rules || typeof rules !== 'object') {
    return rules;
  }

  const normalized = normalizeQueryBuilderRulesForUi(rules);
  const liveValuesByRuleId = {
    inscription_id: [],
    inscription_country: [],
  };

  $(`#${containerId} .rule-container`).each(function() {
    const $rule = $(this);
    const ruleId = $rule.find('.rule-filter-container select').val();
    if (!Object.prototype.hasOwnProperty.call(liveValuesByRuleId, ruleId)) {
      return;
    }

    liveValuesByRuleId[ruleId].push($rule.find('.rule-value-container input.form-control').val() || '');
  });

  const nextValueIndexes = {};
  function visit(rule) {
    if (!rule || typeof rule !== 'object') {
      return;
    }

    if (Array.isArray(rule.rules)) {
      rule.rules.forEach(visit);
      return;
    }

    if (!Object.prototype.hasOwnProperty.call(liveValuesByRuleId, rule.id)) {
      return;
    }

    const nextValueIndex = nextValueIndexes[rule.id] || 0;
    if (nextValueIndex < liveValuesByRuleId[rule.id].length) {
      if (rule.id === 'inscription_id') {
        rule.operator = 'equal';
      }
      rule.value = liveValuesByRuleId[rule.id][nextValueIndex];
      nextValueIndexes[rule.id] = nextValueIndex + 1;
    }
  }

  visit(normalized);
  return normalized;
}

export function getQueryBuilderRulesWithLiveValues(containerId = 'builder') {
  const rules = $(`#${containerId}`).queryBuilder('getRules');
  return applyLiveQueryBuilderValuesToRules(rules, containerId);
}

export function clearRuleValue($rule) {
  const $container = $rule.find('.rule-value-container');

  $container.find('input:not([type=radio]):not([type=checkbox]), textarea').each(function() {
    $(this).val('').trigger('input').trigger('change').trigger('keyup');
  });

  $container.find('select').each(function() {
    const $select = $(this);
    if ($select.data('tomSelect') !== undefined) {
      $select.tomSelect('clear');
    }
    $select.val('').trigger('change');
  });

  const radioGroups = new Set();
  $container.find('input[type=radio]').each(function() {
    const name = $(this).attr('name');
    if (!name || radioGroups.has(name)) {
      return;
    }

    radioGroups.add(name);
    const $group = $container.find(`input[type=radio][name="${name}"]`);
    const $default = $group.filter(function() {
      return this.defaultChecked;
    }).first();
    const $target = $default.length > 0 ? $default : $group.first();
    $group.prop('checked', false);
    $target.prop('checked', true).trigger('change');
  });

  $container.find('input[type=checkbox]').prop('checked', false).trigger('change');
}

/**
 * Gets the minimum and maximum values of a numerical field from a data source
 *
 * @param {Map|Array} dataSource - Either a Map containing database records or an array of items
 * @param {string} fieldName - The name of the field to analyze
 * @returns {Object} Object containing min and max values, or null if field doesn't exist or has no numeric values
 */
export function getMinMaxValues(dataSource, fieldName) {
  if (!dataSource) {
    throw new Error("dataSource parameter is required");
  }

  if (!fieldName || typeof fieldName !== 'string') {
    throw new Error("fieldName parameter is required and must be a string");
  }

  let min = null;
  let max = null;
  let hasValues = false;

  // Function to process each item
  const processItem = (item) => {
    // Skip if item doesn't have the field or value isn't numeric
    if (!item || item[fieldName] === undefined || item[fieldName] === null) {
      return;
    }

    // Convert to number if it's a string
    const value = typeof item[fieldName] === 'string' ?
      parseFloat(item[fieldName]) : item[fieldName];

    // Skip if not a valid number
    if (isNaN(value)) {
      return;
    }

    // Initialize min/max on first valid value
    if (!hasValues) {
      min = value;
      max = value;
      hasValues = true;
      return;
    }

    // Update min/max
    if (value < min) min = value;
    if (value > max) max = value;
  };

  // Handle different data source types
  if (dataSource instanceof Map) {
    // Process Map values
    for (const item of dataSource.values()) {
      processItem(item);
    }
  } else if (Array.isArray(dataSource)) {
    // Process array items
    for (const item of dataSource) {
      processItem(item);
    }
  } else {
    throw new Error("dataSource must be either a Map or an Array");
  }

  return hasValues ? { min, max } : null;
}

export function getValuesFromAllData(term, suggest, fieldName, dbMap, isTomSelect = false) {
  // Get all unique values from dbMap for the specified fieldName
  let allValues = [];
  const uniqueTracker = new Set();
  let nextArtificialId = 20000; // Starting ID for aliases

  Array.from(dbMap.values()).forEach(item => {
    const visited = uniqueTracker.has(item[fieldName]);
    if (item[fieldName] && item[fieldName] !== '' && !visited) {
      uniqueTracker.add(item[fieldName]);
      allValues.push({
        text: item[fieldName],
        id: item[fieldName],
        score: item.id || 0
      });
      if (fieldName === 'signature_text' && item.aliases) {
        const aliases = item.aliases.split('|').map(a => a.trim()).filter(a => a);

        // Add each alias with an artificial ID
        aliases.forEach(alias => {
          if (!uniqueTracker.has(alias)) {
            uniqueTracker.add(alias);
            allValues.push({
              text: alias,
              id: alias,
              score: nextArtificialId++,
            });
          }
        });
      }
    }
  });

  allValues.sort((a, b) => a.score - b.score);

  // Comparison without diacritics:
  if (term !== '') {
    // Normalize strings to remove diacritics
    const normalizedTerm = term.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    allValues = allValues.filter(item => {
      const normalizedText = item.text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
      return normalizedText.includes(normalizedTerm);
    });
  }

  if (isTomSelect) {
    suggest(allValues);
    return allValues;
  }

  const values = allValues.map(item => item.text);
  suggest(values);
  return values;
}


/**
 * Creates an autocomplete configuration object for QueryBuilder.
 *
 * @param {string} ruleId - The unique identifier for the rule.
 * @param {Map} dbMap - A Map containing the database values for autocomplete.
 * @param {Function} humanNameGetter - Function that returns a human-readable name for the given rule ID.
 * @param {Object} [opt={}] - Optional configuration parameters.
 * @param {string} [opt.fieldId] - The field ID to use (defaults to ruleId if not provided).
 * @param {string[]} [opt.operators] - Array of operators to use with this field.
 * @param {string} [opt.type='string'] - The data type for the field.
 * @param {number} [opt.size=100] - The display size of the field.
 * @param {string} [opt.optgroup='other'] - The option group to which this field belongs.
 * @returns {Object} Configuration object for QueryBuilder autocomplete field.
 * @throws {Error} If required parameters are missing or invalid.
 */
function prepareAutoComplete(ruleId, dbMap, humanNameGetter, opt = {}) {
  // Check required arguments
  if (ruleId === undefined) {
    throw new Error("prepareAutoComplete: 'ruleId' parameter is required");
  }
  if (!dbMap || !(dbMap instanceof Map)) {
    throw new Error("prepareAutoComplete: 'dbMap' parameter is required and must be a Map");
  }
  if (!humanNameGetter || typeof humanNameGetter !== 'function') {
    throw new Error("prepareAutoComplete: 'humanNameGetter' parameter is required and must be a function");
  }

  const fieldId = opt.fieldId || ruleId;
  const operators = opt.operators || ["contains", "not_contains",
        'equal', 'not_equal', 'begins_with', "not_begins_with",
        "ends_with", "not_ends_with", "is_empty", 'is_not_empty'];
  const type = opt.type || 'string';
  const size = opt.size || 100;
  const optgroup = opt.optgroup || "other";

  return {
    id: ruleId,
    field: fieldId,
    optgroup: optgroup,
    label: humanNameGetter(ruleId),
    type: type,
    plugin: 'autoComplete',
    plugin_config: {
      minChars: 0,
      delay: 100,
      source: function (term, suggest) {
        getValuesFromAllData(term, suggest, fieldId, dbMap);
      },
      menuClass: ' clusterize-content ',
      attachToParent: true,
    },
    size: size,
    operators: operators,
  }
}

/**
 * Creates a jQuery QueryBuilder filter configuration for integer rules
 *
 * @param {string} ruleId - ID for the rule/filter
 * @param {Map} dbMap - A Map containing the database values for autocomplete.
 * @param {Function} humanNameGetter - Function that returns a human-readable name for the given rule ID.
 * @param {Object} opt - Optional configuration parameters
 * @param {string} opt.fieldId - Field name in data (defaults to ruleId if not provided)
 * @param {Array} opt.operators - Array of operators to use for this filter
 * @param {number} opt.size - Size attribute for the input field
 * @param {string} opt.optgroup - Group to which this filter belongs
 * @param {number} opt.min - Minimum allowed value (optional)
 * @param {number} opt.max - Maximum allowed value (optional)
 * @param {number} opt.step - Step value for input (optional)
 * @param {number} opt.default_value - Default value for the field (optional)
 * @returns {Object} Filter configuration object for QueryBuilder
 */
function prepareIntegerRule(ruleId, dbMap, humanNameGetter, opt) {
  // Check required arguments
  if (ruleId === undefined) {
    throw new Error("prepareIntegerRule: 'ruleId' parameter is required");
  }
  if (!dbMap || !(dbMap instanceof Map)) {
    throw new Error("prepareIntegerRule: 'dbMap' parameter is required and must be a Map");
  }
  if (!humanNameGetter || typeof humanNameGetter !== 'function') {
    throw new Error("prepareIntegerRule: 'humanNameGetter' parameter is required and must be a function");
  }
  if (!opt) opt = {};
  const fieldId = opt.fieldId || ruleId;
  const operators = opt.operators || ['equal', 'not_equal', 'less', 'less_or_equal', 'greater', 'greater_or_equal', 'between', 'not_between'];
  const size = opt.size || 10;
  const optgroup = opt.optgroup || "other";
  const inputType = opt.input || 'number';

  let config = {
    id: ruleId,
    field: fieldId,
    optgroup: optgroup,
    label: humanNameGetter(fieldId),
    type: 'integer',
    size: size,
    operators: operators,
    input: inputType
  };
  const dataLimitValues = getMinMaxValues(dbMap, fieldId);
  opt.min = opt.min || (dataLimitValues && dataLimitValues.min);
  opt.max = opt.max || (dataLimitValues && dataLimitValues.max);

  // Add validation if any constraints are specified
  if (opt.min !== undefined || opt.max !== undefined || opt.step !== undefined) {
    config.validation = {
      allow_empty_value: true
    };

    if (opt.min !== undefined) config.validation.min = opt.min;
    if (opt.max !== undefined) config.validation.max = opt.max;
    if (opt.step !== undefined) config.validation.step = opt.step;
  }

  // Add default value if provided
  if (opt.default_value !== undefined) {
    config.default_value = opt.default_value;
  }

  return config;
}


/**
 * Creates a rule for word search in runic texts
 *
 * @param {Object} config Configuration object
 * @param {string} config.id Rule ID
 * @param {string} config.field Field name in data
 * @param {string} config.label Human-readable label
 * @param {string} config.optgroup Option group
 * @param {string[]} config.operators Array of supported operators
 * @returns {Object} Configured QueryBuilder rule
 */
function createWordSearchRule(config) {
  const input1Label = "Normalization";
  const input2Label = "Transliteration";
  return {
    id: config.id,
    field: config.field,
    label: config.label,
    type: 'string',
    optgroup: config.optgroup || 'gr_texts',
    data: {
      multiField: true,
    },
    input: function(rule, name) {
      return `
        <div class="form-group word-search-rule-value">
          <div class="input-group mb-3 pt-2 word-search-field-group">
            <span class="input-group-text" id="${name}_normalization_input_span">${input1Label}</span>
            <input type="text" id="${name}_normalizationInput" class="form-control" placeholder="" aria-label="${input1Label}" aria-describedby="${name}_normalization_input_span">
            <button type="button" class="btn btn-outline-secondary word-search-clear-btn" data-clear-word-input aria-label="Clear normalization" title="Clear normalization">
              <i class="bi-x-lg"></i>
            </button>
          </div>
          <div class="input-group word-search-field-group">
            <span class="input-group-text" id="${name}_transliteration_input_span">${input2Label}</span>
            <input type="text" id="${name}_transliterationInput" class="form-control" placeholder="" aria-label="${input2Label}" aria-describedby="${name}_transliteration_input_span">
            <button type="button" class="btn btn-outline-secondary word-search-clear-btn" data-clear-word-input aria-label="Clear transliteration" title="Clear transliteration">
              <i class="bi-x-lg"></i>
            </button>
          </div>
          <div class="mt-2">
            <div class="form-check form-check-inline">
              <input class="form-check-input" type="radio" name="${name}_personalNamesMode" value="includeAll" id="${name}_includeAddInput" checked>
              <label class="form-check-label" for="${name}_includeAddInput">Include names</label>
            </div>
            <div class="form-check form-check-inline">
              <input class="form-check-input" type="radio" name="${name}_personalNamesMode" value="excludeNames" id="${name}_excludeNamesInput">
              <label class="form-check-label" for="${name}_excludeNamesInput">Exclude names</label>
            </div>
            <div class="form-check form-check-inline">
              <input class="form-check-input" type="radio" name="${name}_personalNamesMode" value="namesOnly" id="${name}_namesOnlyInput">
              <label class="form-check-label" for="${name}_namesOnlyInput">Only names</label>
            </div>
          </div>
        </div>
      `;
    },
    operators: config.operators || ['contains', 'equal', 'begins_with', 'ends_with'],
    valueGetter: function(rule) {
      var $container = rule.$el.find('.rule-value-container');
      return {
        normalization: $container.find('[id$=_normalizationInput]').val(),
        transliteration: $container.find('[id$=_transliterationInput]').val(),
        names_mode: $container.find('[name$=_personalNamesMode]:checked').val()
      };
    },
    valueSetter: function(rule, value) {
      const names_mode = value.names_mode || 'includeAll';
      var $container = rule.$el.find('.rule-value-container');
      $container.find('[id$=_normalizationInput]').val(value.normalization || '');
      $container.find('[id$=_transliterationInput]').val(value.transliteration || '');
      $container.find('[name$=_personalNamesMode][value="' + names_mode + '"]').prop('checked', true);
    }
  };
}

/*export const rundataOperators = [
  { type: 'texts_contains', nb_inputs: 2, multiple: false, apply_to: ['string'] },
  { type: 'texts_equal', nb_inputs: 2, multiple: false, apply_to: ['string'] },
  { type: 'texts_begins_with', nb_inputs: 2, multiple: false, apply_to: ['string'] },
  { type: 'texts_ends_with', nb_inputs: 2, multiple: false, apply_to: ['string'] },
];*/

export function initQueryBuilder(containerId, viewModel, getHumanName) {
  const dbMap = viewModel.getAllInscriptions();
  const queryBuilder = $(`#${containerId}`);

  const qbOperators = $.fn.queryBuilder.constructor.DEFAULTS.operators.concat([
    // Add to default operators
    { type: 'in_separated_list', nb_inputs: 1, multiple: false, apply_to: ['string'] },
    { type: 'cross_form', nb_inputs: 1, multiple: false, apply_to: ['string'] },
  ]);
  const qbLang = {
    operators: {
      'in_separated_list': "is in list",
      'cross_form': " ",
    }
  };
  const qbSqlOperators = {
    'in_separated_list': { 'op': 'IN', mod: '{0}' },
    'cross_form': { 'op': 'IN' },
  };

  let queryBuilderFilters = [
    // gr_inscription filters
    {
      id: 'inscription_id',
      optgroup: 'gr_inscription',
      field: 'signature_text',
      label: getHumanName('signature_text'),
      type: 'string',
      input: function(rule, name) {
        return `<input type="text" name="${name}" class="form-control" autocomplete="off">`;
      },
      operators: [
        'equal', 'begins_with', 'not_begins_with',
        'ends_with', 'not_ends_with', 'contains', 'not_contains',
      ],
      validation: {
        callback: function(value) {
          return true;
        },
      },
      valueGetter: function (rule) {
        return rule.$el.find('.rule-value-container input.form-control').val() || '';
      },
      valueSetter: function (rule, value) {
        rule.$el.find('.rule-value-container input.form-control').val(value || '');
      },
    },
    {
      id: 'lost',
      label: getHumanName('lost'),
      field: 'lost',
      optgroup: 'gr_inscription',
      type: 'integer',
      input: 'radio',
      values: [
        {0: 'No'},
        {1: 'Yes'},
      ],
      default_value: 0,
      operators: ['equal'],
    },
    // gr_texts filters
    createWordSearchRule({
      id: 'normalization_norse_to_transliteration',
      field: 'normalization_norse',
      label: 'Transliteration and Normalization "Old Norse"',
      optgroup: 'gr_texts',
    }),
    createWordSearchRule({
      id: 'normalization_scandinavian_to_transliteration',
      field: 'normalisation_scandinavian',
      label: 'Transliteration and Normalization "Old Scandinavian"',
      optgroup: 'gr_texts',
    }),
    prepareAutoComplete('english_translation', dbMap, getHumanName, { optgroup: 'gr_texts', operators: ["contains", "not_contains", "is_empty", 'is_not_empty'] }),
    prepareAutoComplete('swedish_translation', dbMap, getHumanName, { optgroup: 'gr_texts', operators: ["contains", "not_contains", "is_empty", 'is_not_empty'] }),
    {
      id: 'search_runic_texts',
      field: 'normalisation_norse',
      label: 'Search in runic texts',
      type: 'string',
      input: 'text',
      optgroup: 'gr_texts',
      data: {
        multiField: true,
      },
      operators: ['contains', 'equal', 'begins_with', 'ends_with'],
    },
    {
      id: 'has_personal_name',
      label: "Contains names",
      field: 'num_names',
      optgroup: 'gr_texts',
      type: 'integer',
      input: 'radio',
      values: [
        {0: 'No'},
        {1: 'Yes'},
      ],
      default_value: 1,
      operators: ['equal'],
    },
    // gr_location filters
    {
      id: 'inscription_country',
      optgroup: "gr_location",
      field: 'signature_text',
      label: 'Country or Swedish Province',
      type: 'string',
      input: function(rule, name) {
        return `<input type="text" name="${name}" class="form-control" autocomplete="off">`;
      },
      data: {
        multiField: true,
      },
      operators: isCompactDbLayout()
        ? ['in', 'contains']
        : ['in'],
      plugin: 'autoComplete',
      plugin_config: {
        minChars: 1,
        delay: 100,
        cache: 0,
        source: function(term, suggest) {
          suggest(getCountryProvinceSuggestions(term));
        },
        menuClass: 'clusterize-content',
        attachToParent: true,
      },
      validation: {
        callback: function(value) {
          return true;
        },
      },
      valueGetter: function (rule) {
        return rule.$el.find('.rule-value-container input.form-control').val() || '';
      },
      valueSetter: function (rule, value) {
        rule.$el.find('.rule-value-container input.form-control').val(formatCountryProvinceRuleValue(value));
      }
    },
    prepareAutoComplete('full_address', dbMap, getHumanName, { optgroup: 'gr_location', operators: ['contains'] }),
    prepareAutoComplete('found_location', dbMap, getHumanName, { optgroup: 'gr_location' }),
    prepareAutoComplete('parish', dbMap, getHumanName, { optgroup: 'gr_location' }),
    prepareAutoComplete('district', dbMap, getHumanName, { optgroup: 'gr_location' }),
    prepareAutoComplete('municipality', dbMap, getHumanName, { optgroup: 'gr_location' }),
    prepareAutoComplete('current_location', dbMap, getHumanName, { optgroup: 'gr_location' }),
    prepareAutoComplete('original_site', dbMap, getHumanName, { optgroup: 'gr_location' }),
    prepareAutoComplete('parish_code', dbMap, getHumanName, { optgroup: 'gr_location' }),
    // gr_time_period filters
    prepareAutoComplete('dating', dbMap, getHumanName, { optgroup: 'gr_time_period' }),
    prepareIntegerRule('year_from', dbMap, getHumanName, { operators: ['equal', 'less', 'greater', 'between'], optgroup: 'gr_time_period' }),
    prepareIntegerRule('year_to', dbMap, getHumanName, { operators: ['equal', 'less', 'greater', 'between'], optgroup: 'gr_time_period' }),
    prepareAutoComplete('style', dbMap, getHumanName, { optgroup: 'gr_time_period' }),
    // gr_design filters
    prepareAutoComplete('carver', dbMap, getHumanName, { optgroup: 'gr_design' }),
    prepareAutoComplete('rune_type', dbMap, getHumanName, { optgroup: 'gr_design' }),
    prepareAutoComplete('material', dbMap, getHumanName, { optgroup: 'gr_design' }),
    prepareAutoComplete('material_type', dbMap, getHumanName, { optgroup: 'gr_design' }),
    prepareAutoComplete('objectInfo', dbMap, getHumanName, { optgroup: 'gr_design' }),
    prepareIntegerRule('num_crosses', dbMap, getHumanName,
      {
        operators: ['equal', 'not_equal', 'less', 'less_or_equal', 'greater', 'greater_or_equal', 'between'],
        optgroup: 'gr_design',
        default_value: 0,
        step: 1,
      }
    ),
    {
      id: 'cross_form',
      field: 'crosses',
      label: getHumanName('cross_form'),
      operators: ['cross_form'],
      optgroup: 'gr_design',
      input: function (rule, name) {
        // this is a bit of a hack as getValuesFromAllData function is intended for other use
        const allCrossForms = viewModel.getAllCrossForms().map(item => {
          return `<option value="${item}">${item}</option>`;
        }).join('');
        return `
          <select name="${name}_1" class="form-select" aria-label="Cross form">${allCrossForms}</select>
          <div>Certain?
            <div class="form-check form-check-inline">
              <input type="radio" name="${name}_2" value="0" class="form-check-input" id="${name}_2_0">
              <label for="${name}_2_0" class="form-check-label">No</label>
            </div>

            <div class="form-check form-check-inline">
              <input type="radio" name="${name}_2" value="1" class="form-check-input" id="${name}_2_1">
              <label for="${name}_2_1" class="form-check-label">Yes</label>
            </div>

            <div class="form-check form-check-inline">
              <input type="radio" name="${name}_2" value="2" class="form-check-input" id="${name}_2_2" checked>
              <label for="${name}_2_2" class="form-check-label">Doesn't matter</label>
            </div>
          </div>`;
      },
      valueGetter: function (rule) {
        const val1 = rule.$el.find('.rule-value-container [name$=_1]').val();
        const val2 = rule.$el.find('.rule-value-container [name$=_2]:checked').val();
        return {form: val1, is_certain: val2};
      },
      valueSetter: function (rule, value) {
        $(rule.$el.find('.rule-value-container [name$=_1]')[0]).val(value.form);
        rule.$el.find(`.rule-value-container [name$=_2][value=${value.is_certain}]`).prop('checked', true);
      },
    },
    // gr_more_info filters
    prepareAutoComplete('references_combined', dbMap, getHumanName, { optgroup: 'gr_more_info' }),
    prepareAutoComplete('additional', dbMap, getHumanName, { optgroup: 'gr_more_info' }),
  ];

  const my_rule_template = ({ rule_id, icons, settings, translate, builder }) => {
    return `
  <div id="${rule_id}" class="rule-container d-flex align-items-center w-100">
    <div class="rule-header">
    </div>
    ${settings.display_errors ? `
      <div class="error-container flex-shrink-0"><i class="${icons.error}"></i></div>
    ` : ''}
    <div class="rule-filter-container flex-shrink-0"></div>
    <div class="rule-operator-container flex-shrink-0"></div>
    <div class="rule-value-container flex-grow-1 me-2"></div>
    <button type="button" class="btn btn-sm btn-outline-secondary rule-clear-value-btn flex-shrink-0" data-clear="rule-value" aria-label="Clear rule value" title="Clear value">
      <i class="bi-x-lg"></i>
    </button>
    <div class="rule-footer d-flex flex-wrap align-items-center gap-1 ms-auto">
      <div class="d-flex flex-wrap gap-1 rule-actions">
        <button type="button" class="btn btn-sm btn-outline-danger rule-remove-btn" data-delete="rule" aria-label="Remove rule" title="Remove rule">
          <i class="bi-trash"></i><span class="visually-hidden">${translate("delete_rule")}</span>
        </button>
      </div>
    </div>
  </div>`;
  };

  // Filters are already sorted in the correct order to match optGroups.
  // The sortGroupsByOrder function is kept for redundancy to ensure alphabetical
  // sorting within each group.
  queryBuilderFilters = sortGroupsByOrder(queryBuilderFilters, Object.keys(optGroups));

  queryBuilder.queryBuilder({
    display_empty_filter: false,
    //operators: $.fn.queryBuilder.constructor.DEFAULTS.operators.concat(rundataOperators),

    plugins: queryBuilderPlugins,
    filters: queryBuilderFilters,
    sort_filters: false,
    allow_empty: false,
    optgroups: optGroups,

    operators: qbOperators,
    lang: qbLang,
    sqlOperators: qbSqlOperators,

    templates: {
      rule: my_rule_template,
    },
  });

  queryBuilder.on('click', '[data-clear="rule-value"]', function(e) {
    e.preventDefault();
    const $rule = $(this).closest($.fn.queryBuilder.constructor.selectors.rule_container);
    clearRuleValue($rule);
  });

  queryBuilder.on('click', '[data-clear-word-input]', function(e) {
    e.preventDefault();
    $(this)
      .closest('.word-search-field-group')
      .find('input.form-control')
      .val('')
      .trigger('input')
      .trigger('change')
      .trigger('keyup');
  });

  function updateRuleActionLayout(rule) {
    const isWordSearchRule = rule && rule.filter && [
      'normalization_norse_to_transliteration',
      'normalization_scandinavian_to_transliteration',
    ].includes(rule.filter.id);
    rule.$el.toggleClass('rule-word-search', !!isWordSearchRule);
  }

  function updateGroupDeleteButtons() {
    queryBuilder.find('[data-delete="group"]').each(function() {
      const $button = $(this);
      const $group = $button.closest('.rules-group-container');
      const isRootGroup = $group.attr('id') === `${containerId}_group_0`;

      $button.toggleClass('group-remove-btn', !isRootGroup);
      if (isRootGroup || $button.data('groupDeleteDecorated')) {
        return;
      }

      $button
        .data('groupDeleteDecorated', true)
        .removeClass('btn-danger')
        .addClass('btn-outline-danger')
        .attr({
          'aria-label': 'Remove group',
          title: 'Remove group',
        })
        .html('<i class="bi-trash"></i><span class="visually-hidden">Delete group</span>');
    });
  }

  updateGroupDeleteButtons();

  const queryBuilderElement = queryBuilder.get(0);
  if (queryBuilderElement && typeof MutationObserver !== 'undefined') {
    const groupDeleteObserver = new MutationObserver(updateGroupDeleteButtons);
    groupDeleteObserver.observe(queryBuilderElement, { childList: true, subtree: true });
  }

  function updateSignatureIdOperatorLabel(rule) {
    if (!rule || !rule.filter || rule.filter.id !== 'inscription_id') {
      return;
    }
    rule.$el.find('.rule-operator-container option[value="equal"]').text('is in list');
  }

  function updateSignatureIdOperatorLabelsInDom() {
    queryBuilder.find('.rule-container').each(function() {
      const $rule = $(this);
      if ($rule.find('.rule-filter-container select').val() === 'inscription_id') {
        $rule.find('.rule-operator-container option[value="equal"]').text('is in list');
      }
    });
  }

  // Event handler when rule is created and rule operator is changed
  queryBuilder.on('afterCreateRuleInput.queryBuilder afterUpdateRuleFilter.queryBuilder afterUpdateRuleOperator.queryBuilder', function(e, rule) {
    updateRuleActionLayout(rule);
    if (rule && rule.filter && rule.filter.id === 'inscription_id') {
      updateSignatureIdOperatorLabel(rule);
      updateSignatureIdOperatorLabelsInDom();
    }
  });

  updateSignatureIdOperatorLabelsInDom();
}
