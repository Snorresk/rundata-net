// Key in the local storage under which users display options are saved.
// display options are information which is displayed per inscription.
const gUserSelectedDisplayKey = "userSelectedDisplay";
const gShowHeadersKey = "showHeaders";
const gMobileDisplayDefaultsVersionKey = "mobileDisplayDefaultsVersion";
const MOBILE_DISPLAY_DEFAULTS_VERSION = "20260603-mobile-property-order";
const REQUIRED_DISPLAY_VALUES = ['coordination'];
const DEFAULT_SELECTED_DISPLAY_VALUES = [
  'signature_text', 'transliteration', 'normalisation_scandinavian', 'normalisation_norse',
  'english_translation', 'swedish_translation', 'found_location', 'parish', 'municipality', 'district', 'current_location',
  'original_site', 'coordination', 'images', 'rune_type', 'carver', 'num_crosses', 'cross_form', 'dating', 'style',
  'material_type', 'material', 'objectInfo', 'references_combined', 'additional'
];
const MOBILE_DEFAULT_SELECTED_DISPLAY_VALUES = [
  'signature_text',
  'images',
  'objectInfo',
  'lost',
  'dating',
  'transliteration',
  'normalisation_norse',
  'normalisation_scandinavian',
  'english_translation',
  'swedish_translation',
  'found_location',
  'parish',
  'district',
  'municipality',
  'coordination',
  'carver',
  'style',
  'rune_type',
  'num_crosses',
  'cross_form',
  'additional',
  'references_combined',
];
const DISPLAY_FIELD_GROUPS = [
  {
    title: 'Inscription',
    fields: ['signature_text', 'lost', 'images'],
  },
  {
    title: 'Runic Texts',
    fields: ['transliteration', 'normalisation_scandinavian', 'normalisation_norse', 'english_translation', 'swedish_translation'],
  },
  {
    title: 'Location',
    fields: ['full_address', 'found_location', 'parish', 'municipality', 'district', 'current_location', 'original_site', 'coordination', 'parish_code'],
  },
  {
    title: 'Dating',
    fields: ['dating', 'year_from', 'year_to', 'style'],
  },
  {
    title: 'Design and Object',
    fields: ['rune_type', 'carver', 'num_crosses', 'cross_form', 'material_type', 'material', 'objectInfo'],
  },
  {
    title: 'References and Other',
    fields: ['references_combined', 'additional'],
  },
];

function normalizeSelectedValues(selectedValues) {
  const normalized = Array.isArray(selectedValues) ? [...selectedValues] : [...DEFAULT_SELECTED_DISPLAY_VALUES];
  REQUIRED_DISPLAY_VALUES.forEach(requiredValue => {
    if (!normalized.includes(requiredValue)) {
      normalized.push(requiredValue);
    }
  });
  return normalized;
}

function applyMobileDefaultMigration(selectedValues, storage) {
  const normalized = normalizeSelectedValues(selectedValues);
  if (!shouldUseMobileDefaults() || !storage) {
    return normalized;
  }
  if (storage.getItem(gMobileDisplayDefaultsVersionKey) === MOBILE_DISPLAY_DEFAULTS_VERSION) {
    return normalized;
  }

  const selectedSet = new Set(normalized);
  const orderedDefaults = MOBILE_DEFAULT_SELECTED_DISPLAY_VALUES.filter(value => selectedSet.has(value) || !normalized.includes(value));
  const remainingSelected = normalized.filter(value => !orderedDefaults.includes(value));
  const migratedValues = [...orderedDefaults, ...remainingSelected];
  storage.setItem(gMobileDisplayDefaultsVersionKey, MOBILE_DISPLAY_DEFAULTS_VERSION);
  storage.setItem(gUserSelectedDisplayKey, JSON.stringify(migratedValues));
  return migratedValues;
}

function shouldUseMobileDefaults() {
  try {
    return window.matchMedia('(max-width: 767.98px)').matches;
  } catch (e) {
    return false;
  }
}

function isMobileDisplayOptionsUi() {
  return shouldUseMobileDefaults();
}

function getDefaultSelectedDisplayValues() {
  return shouldUseMobileDefaults()
    ? MOBILE_DEFAULT_SELECTED_DISPLAY_VALUES
    : DEFAULT_SELECTED_DISPLAY_VALUES;
}

function storageAvailable(type) {
  let storage;
  try {
    storage = window[type];
    const x = '__storage_test__';
    storage.setItem(x, x);
    storage.removeItem(x);
    return true;
  }
  catch(e) {
    return e instanceof DOMException && (
      // everything except Firefox
      e.code === 22 ||
      // Firefox
      e.code === 1014 ||
      // test name field too, because code might not be present
      // everything except Firefox
      e.name === 'QuotaExceededError' ||
      // Firefox
      e.name === 'NS_ERROR_DOM_QUOTA_REACHED') &&
      // acknowledge QuotaExceededError only if there's something already stored
      (storage && storage.length !== 0);
  }
}

export function getUserSelectedDisplay() {
  if (!storageAvailable('localStorage')) {
    const fallbackDefaults = getDefaultSelectedDisplayValues();
    return normalizeSelectedValues(fallbackDefaults);
  }

  try {
    const storage = window['localStorage'];
    if (storage.getItem(gUserSelectedDisplayKey)) {
      return normalizeSelectedValues(JSON.parse(storage.getItem(gUserSelectedDisplayKey)));
    }
  } catch (e) {
    console.error('Error while reading user selected display from local storage:', e);
  }

  const fallbackDefaults = getDefaultSelectedDisplayValues();
  return normalizeSelectedValues(fallbackDefaults);
}

export function saveUserSelectedDisplay(selectedValues = null) {
  if (!storageAvailable('localStorage')) {
    return;
  }
  const storage = window['localStorage'];

  //var selectedValues = $('#multiselect_to option').map((index, el) => $(el).val()).toArray();
  // ensure it is an array and encode it as json string, because local storage can work with string only.
  const selectedValuesArray = JSON.stringify(selectedValues ? [].concat(selectedValues) : []);

  storage.setItem(gUserSelectedDisplayKey, selectedValuesArray);
}

export function getUserSelectedFields() {
  const selectedValues = getUserSelectedDisplay();
  return selectedValues
    .map(value => schemaFieldsInfo.find(prop => prop.schemaName === value))
    .filter(Boolean);
}


function getSchemaField(schemaName) {
  return schemaFieldsInfo.find(prop => prop.schemaName === schemaName);
}

function getChecklistSelectedValues() {
  return $('#displayOptionsChecklist input[data-display-field]:checked')
    .map((index, el) => $(el).attr('data-display-field'))
    .toArray();
}

function renderDisplayOptionRow(field, selectedSet) {
  const isRequired = REQUIRED_DISPLAY_VALUES.includes(field.schemaName);
  const isChecked = isRequired || selectedSet.has(field.schemaName);
  const disabledAttr = isRequired ? 'disabled' : '';
  const requiredHint = isRequired ? ' <span class="text-muted">(always shown)</span>' : '';
  return `
    <div class="display-options-mobile-row" data-display-option-row="${field.schemaName}">
      <div class="form-check mb-0 flex-grow-1">
        <input class="form-check-input" type="checkbox" data-display-field="${field.schemaName}" id="displayField_${field.schemaName}" ${isChecked ? 'checked' : ''} ${disabledAttr}>
        <label class="form-check-label" for="displayField_${field.schemaName}">${field.text['en']}${requiredHint}</label>
      </div>
      <div class="display-options-mobile-order" aria-label="Move ${field.text['en']}">
        <button type="button" class="btn btn-outline-secondary btn-sm" data-display-move="up" data-display-field="${field.schemaName}" aria-label="Move ${field.text['en']} up">
          <i class="bi bi-chevron-up" aria-hidden="true"></i>
        </button>
        <button type="button" class="btn btn-outline-secondary btn-sm" data-display-move="down" data-display-field="${field.schemaName}" aria-label="Move ${field.text['en']} down">
          <i class="bi bi-chevron-down" aria-hidden="true"></i>
        </button>
      </div>
    </div>
  `;
}

function updateMobileDisplayOrderButtons() {
  const rows = Array.from(document.querySelectorAll('#displayOptionsChecklist [data-display-option-row]'));
  rows.forEach((row, index) => {
    const upButton = row.querySelector('[data-display-move="up"]');
    const downButton = row.querySelector('[data-display-move="down"]');
    if (upButton) {
      upButton.disabled = index === 0;
    }
    if (downButton) {
      downButton.disabled = index === rows.length - 1;
    }
  });
}

function renderMobileDisplayOptionsChecklist(selectedValues) {
  const selectedSet = new Set(normalizeSelectedValues(selectedValues));
  const $checklist = $('#displayOptionsChecklist');
  $checklist.empty();

  const orderedFieldNames = [
    ...normalizeSelectedValues(selectedValues),
    ...schemaFieldsInfo
      .map(field => field.schemaName)
      .filter(schemaName => !selectedSet.has(schemaName)),
  ];
  const usedFields = new Set();
  orderedFieldNames.forEach(schemaName => {
    if (usedFields.has(schemaName)) {
      return;
    }
    const field = getSchemaField(schemaName);
    if (!field) {
      return;
    }
    usedFields.add(schemaName);
    $checklist.append(renderDisplayOptionRow(field, selectedSet));
  });
  updateMobileDisplayOrderButtons();
}

function renderGroupedDisplayOptionsChecklist(selectedValues) {
  const selectedSet = new Set(normalizeSelectedValues(selectedValues));
  const usedFields = new Set();
  const $checklist = $('#displayOptionsChecklist');
  $checklist.empty();

  DISPLAY_FIELD_GROUPS.forEach(group => {
    const groupFields = group.fields
      .map(name => getSchemaField(name))
      .filter(Boolean);
    if (groupFields.length === 0) {
      return;
    }
    const $group = $('<div class="display-options-group"></div>');
    $group.append(`<h6 class="display-options-group-title">${group.title}</h6>`);

    groupFields.forEach(field => {
      usedFields.add(field.schemaName);
      const isRequired = REQUIRED_DISPLAY_VALUES.includes(field.schemaName);
      const isChecked = isRequired || selectedSet.has(field.schemaName);
      const disabledAttr = isRequired ? 'disabled' : '';
      const requiredHint = isRequired ? ' <span class="text-muted">(always shown)</span>' : '';
      const rowHtml = `
        <div class="form-check mb-1">
          <input class="form-check-input" type="checkbox" data-display-field="${field.schemaName}" id="displayField_${field.schemaName}" ${isChecked ? 'checked' : ''} ${disabledAttr}>
          <label class="form-check-label" for="displayField_${field.schemaName}">${field.text['en']}${requiredHint}</label>
        </div>
      `;
      $group.append(rowHtml);
    });

    $checklist.append($group);
  });

  const remainingFields = schemaFieldsInfo.filter(field => !usedFields.has(field.schemaName));
  if (remainingFields.length > 0) {
    const $otherGroup = $('<div class="display-options-group"></div>');
    $otherGroup.append('<h6 class="display-options-group-title">Other</h6>');
    remainingFields.forEach(field => {
      const isRequired = REQUIRED_DISPLAY_VALUES.includes(field.schemaName);
      const isChecked = isRequired || selectedSet.has(field.schemaName);
      const disabledAttr = isRequired ? 'disabled' : '';
      const requiredHint = isRequired ? ' <span class="text-muted">(always shown)</span>' : '';
      const rowHtml = `
        <div class="form-check mb-1">
          <input class="form-check-input" type="checkbox" data-display-field="${field.schemaName}" id="displayField_${field.schemaName}" ${isChecked ? 'checked' : ''} ${disabledAttr}>
          <label class="form-check-label" for="displayField_${field.schemaName}">${field.text['en']}${requiredHint}</label>
        </div>
      `;
      $otherGroup.append(rowHtml);
    });
    $checklist.append($otherGroup);
  }
}

function renderDisplayOptionsChecklist(selectedValues) {
  if (isMobileDisplayOptionsUi()) {
    renderMobileDisplayOptionsChecklist(selectedValues);
    return;
  }
  renderGroupedDisplayOptionsChecklist(selectedValues);
}

function setDesktopMultiselectOptions(selectedValues) {
  let sortValue = 0;
  $('#multiselect_to').empty();
  $('#multiselect').empty();

  // Populate the list of already selected display options
  selectedValues.forEach(value => {
    const schemaField = schemaFieldsInfo.find(prop => prop.schemaName === value);
    if (schemaField) {
      $('#multiselect_to').append($('<option>', {
        value: schemaField.schemaName,
        text : schemaField.text['en'],
        sortValue: sortValue++,
      }));
    }
  });

  // Populate the list of available display options
  schemaFieldsInfo.forEach(schemaField => {
    if (selectedValues.indexOf(schemaField.schemaName) === -1) {
      $('#multiselect').append($('<option>', {
        value: schemaField.schemaName,
        text : schemaField.text['en'],
        sortValue: sortValue++,
      }));
    }
  });
}

function getCurrentSelectedValues() {
  if (isMobileDisplayOptionsUi()) {
    return getChecklistSelectedValues();
  }
  return $('#multiselect_to option').map((index, el) => $(el).val()).toArray();
}

function setMultiselectOptions(selectedValues, showHeaders) {
  setDesktopMultiselectOptions(selectedValues);
  renderDisplayOptionsChecklist(selectedValues);

  if (typeof showHeaders !== 'boolean') {
    showHeaders = showHeaders === 'true';
  }
  $('#chkDisplayHeaders').prop('checked', showHeaders);
}

function applyDisplayFormatChanges({ closeDialog = false } = {}) {
  const alertObj = $('#formatDialogAlertObj');
  const selectedValues = getCurrentSelectedValues();

  if (selectedValues === null || selectedValues.length == 0) {
    alertObj.html('Nothing is selected for display! Please select at least one property.');
    alertObj.show();
    return false;
  }
  alertObj.hide();

  const lastShowHeaders = localStorage.getItem(gShowHeadersKey);
  const lastUserSelectedValues = JSON.parse(localStorage.getItem(gUserSelectedDisplayKey) || '[]');
  const showHeaders = $('#chkDisplayHeaders').is(":checked");
  if (!arraysEqual(lastUserSelectedValues, selectedValues) || lastShowHeaders != String(showHeaders)) {
    saveUserSelectedDisplay(selectedValues);
    localStorage.setItem(gShowHeadersKey, showHeaders);

    // display signature info
    $('#multiselect, #displayOptionsChecklist').trigger('displayUpdated', {message: 'hello'});
  }

  if (closeDialog) {
    document.getElementById('btnDismissDisplayFormat').click();
  }
  return true;
}

function applyMobileDisplayFormatImmediately() {
  if (!isMobileDisplayOptionsUi()) {
    return;
  }
  applyDisplayFormatChanges({ closeDialog: false });
}

function moveMobileDisplayOption(event) {
  const button = event.target.closest('[data-display-move]');
  if (!button || !isMobileDisplayOptionsUi()) {
    return;
  }

  const row = button.closest('[data-display-option-row]');
  if (!row) {
    return;
  }

  if (button.dataset.displayMove === 'up' && row.previousElementSibling) {
    row.parentElement.insertBefore(row, row.previousElementSibling);
  } else if (button.dataset.displayMove === 'down' && row.nextElementSibling) {
    row.parentElement.insertBefore(row.nextElementSibling, row);
  }

  updateMobileDisplayOrderButtons();
  applyMobileDisplayFormatImmediately();
}

/**
 * Preserve the sorting after user interacts with the display options.
 * Reassigns sortValue attributes so the current order is maintained
 * when the multiselect sort function runs after adding/removing items.
 */
export function resortDisplayOptions() {
  let newSort = 0;
  $('#multiselect_to option').each(function() { $(this).attr('sortValue', newSort++); });
  $('#multiselect option').each(function() { $(this).attr('sortValue', newSort++); });
}

export function initMultiselect() {
  const storage = window['localStorage'];
  const savedSelected = storage.getItem(gUserSelectedDisplayKey);
  const defaultValues = getDefaultSelectedDisplayValues();
  const selectedValues = savedSelected
    ? applyMobileDefaultMigration(JSON.parse(savedSelected), storage)
    : normalizeSelectedValues(defaultValues);
  if (!savedSelected && shouldUseMobileDefaults()) {
    storage.setItem(gMobileDisplayDefaultsVersionKey, MOBILE_DISPLAY_DEFAULTS_VERSION);
  }
  const savedShowHeaders = storage.getItem(gShowHeadersKey);
  const showHeaders = savedShowHeaders ? savedShowHeaders === 'true' : true;

  setMultiselectOptions(selectedValues, showHeaders);

  $('#formatDialogAlertObj').hide();

  $('#multiselect').multiselect({
    keepRenderingSortRight: false,
    skipInitSortRight: false,
    sort: {
      left: function (a, b) {
        const aValue = parseInt($(a).attr('sortValue'));
        const bValue = parseInt($(b).attr('sortValue'));

        return aValue > bValue ? 1 : -1;
      },
      right: function (a, b) {
        const aValue = parseInt($(a).attr('sortValue'));
        const bValue = parseInt($(b).attr('sortValue'));

        return aValue > bValue ? 1 : -1;
      }
    },
    afterMoveUp: () => resortDisplayOptions(),
    afterMoveDown: () => resortDisplayOptions(),
    afterMoveToRight: () => resortDisplayOptions(),
    afterMoveToLeft: () => resortDisplayOptions(),
  });

  document.getElementById('btnApplyDisplayFormat').addEventListener('click', onDisplayFormatClicked);
  document.getElementById('displayOptionsChecklist').addEventListener('change', applyMobileDisplayFormatImmediately);
  document.getElementById('displayOptionsChecklist').addEventListener('click', moveMobileDisplayOption);
  document.getElementById('chkDisplayHeaders').addEventListener('change', applyMobileDisplayFormatImmediately);
  document.getElementById('btnDismissDisplayFormat').addEventListener('click', () => {
    // revert the changes
    const savedShowHeaders = localStorage.getItem(gShowHeadersKey);
    const showHeaders = savedShowHeaders ? savedShowHeaders === 'true' : true;
    const savedSelected = localStorage.getItem(gUserSelectedDisplayKey);
    const selectedValues = normalizeSelectedValues(savedSelected ? JSON.parse(savedSelected) : getDefaultSelectedDisplayValues());
    setMultiselectOptions(selectedValues, showHeaders);
  });

  const formatDialogEl = document.getElementById('divFormatDialog')
  formatDialogEl.addEventListener('shown.bs.modal', event => {
    $('#formatDialogAlertObj').hide();

    // preserve current display options in a local storage, so that we may compare it later to detect user edit
    const lastShowHeaders = $('#chkDisplayHeaders').is(":checked");
    const userSelectedDisplay = getCurrentSelectedValues();
    saveUserSelectedDisplay(userSelectedDisplay);
    localStorage.setItem(gShowHeadersKey, lastShowHeaders);
  });
}

function onDisplayFormatClicked(e) {
  e.preventDefault();
  applyDisplayFormatChanges({ closeDialog: true });
}
