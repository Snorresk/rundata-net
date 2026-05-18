// Key in the local storage under which users display options are saved.
// display options are information which is displayed per inscription.
const gUserSelectedDisplayKey = "userSelectedDisplay";
const gShowHeadersKey = "showHeaders";
const REQUIRED_DISPLAY_VALUES = ['coordination'];
const DEFAULT_SELECTED_DISPLAY_VALUES = [
  'signature_text', 'transliteration', 'normalisation_scandinavian', 'normalisation_norse',
  'english_translation', 'swedish_translation', 'found_location', 'parish', 'municipality', 'district', 'current_location',
  'original_site', 'coordination', 'images', 'rune_type', 'carver', 'num_crosses', 'cross_form', 'dating', 'style',
  'material_type', 'material', 'objectInfo', 'references_combined', 'additional'
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
    return normalizeSelectedValues(DEFAULT_SELECTED_DISPLAY_VALUES);
  }

  try {
    const storage = window['localStorage'];
    if (storage.getItem(gUserSelectedDisplayKey)) {
      return normalizeSelectedValues(JSON.parse(storage.getItem(gUserSelectedDisplayKey)));
    }
  } catch (e) {
    console.error('Error while reading user selected display from local storage:', e);
  }

  return normalizeSelectedValues(DEFAULT_SELECTED_DISPLAY_VALUES);
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


function setMultiselectOptions(selectedValues, showHeaders) {
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

  if (typeof showHeaders !== 'boolean') {
    showHeaders = showHeaders === 'true';
  }
  $('#chkDisplayHeaders').prop('checked', showHeaders);
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
  const savedSelected = localStorage.getItem(gUserSelectedDisplayKey);
  const selectedValues = normalizeSelectedValues(savedSelected ? JSON.parse(savedSelected) : DEFAULT_SELECTED_DISPLAY_VALUES);
  const savedShowHeaders = localStorage.getItem(gShowHeadersKey);
  const showHeaders = savedShowHeaders ? savedShowHeaders === 'true' : true;

  setMultiselectOptions(selectedValues, showHeaders);

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

  $('#formatDialogAlertObj').hide();

  document.getElementById('btnApplyDisplayFormat').addEventListener('click', onDisplayFormatClicked);
  document.getElementById('btnDismissDisplayFormat').addEventListener('click', () => {
    // revert the changes
    const savedShowHeaders = localStorage.getItem(gShowHeadersKey);
    const showHeaders = savedShowHeaders ? savedShowHeaders === 'true' : true;
    const savedSelected = localStorage.getItem(gUserSelectedDisplayKey);
    const selectedValues = normalizeSelectedValues(savedSelected ? JSON.parse(savedSelected) : DEFAULT_SELECTED_DISPLAY_VALUES);
    setMultiselectOptions(selectedValues, showHeaders);
  });

  const formatDialogEl = document.getElementById('divFormatDialog')
  formatDialogEl.addEventListener('shown.bs.modal', event => {
    $('#formatDialogAlertObj').hide();

    // preserve current display options in a local storage, so that we may compare it later to detect user edit
    const lastShowHeaders = $('#chkDisplayHeaders').is(":checked");
    const userSelectedDisplay = $('#multiselect_to option').map((index, el) => $(el).val()).toArray();
    saveUserSelectedDisplay(userSelectedDisplay);
    localStorage.setItem(gShowHeadersKey, lastShowHeaders);
  });
}

function onDisplayFormatClicked(e) {
  e.preventDefault();

  const alertObj = $('#formatDialogAlertObj');
  const selectedValues = $('#multiselect_to option').map((index, el) => $(el).val()).toArray();

  if (selectedValues === null || selectedValues.length == 0) {
    alertObj.html('Nothing is selected for display! Please select at least one property.');
    alertObj.show();
    return;
  }
  alertObj.hide();

  // read old values from the local storage
  const lastShowHeaders = localStorage.getItem(gShowHeadersKey);
  const lastUserSelectedValues = JSON.parse(localStorage.getItem(gUserSelectedDisplayKey));

  const showHeaders = $('#chkDisplayHeaders').is(":checked");
  if (!arraysEqual(lastUserSelectedValues, selectedValues) || lastShowHeaders != showHeaders) {
    saveUserSelectedDisplay(selectedValues);
    localStorage.setItem(gShowHeadersKey, showHeaders);

    // display signature info
    $('#multiselect').trigger('displayUpdated', {message: 'hello'});
  }

  $(this).prev().click();
}
