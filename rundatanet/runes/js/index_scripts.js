import { isPersonalName } from './search_core.js';
import { isCompactDbLayout } from './index_layout.js';

export { isPersonalName } from './search_core.js';

export const schemaFieldsInfo = [
  {
    schemaName: 'signature_text',
    text: {
      'en': 'Inscription ID'
    },
  },
  {
    schemaName: 'full_address',
    text: {
      'en': 'Any location',
    },
  },
  {
    schemaName: 'found_location',
    text: {
      'en': 'Found location',
    },
  },
  {
    schemaName: 'parish',
    text: {
      'en': 'Parish',
    },
  },
  {
    schemaName: 'district',
    text: {
      'en': 'District',
    },
  },
  {
    schemaName: 'municipality',
    text: {
      'en': 'Municipality',
    },
  },
  {
    schemaName: 'current_location',
    text: {
      'en': 'Current location',
    },
  },
  {
    schemaName: 'original_site',
    text: {
      en: 'Original site',
    },
  },
  {
    schemaName: 'coordination',
    text: {
      en: 'Coordinates',
    },
  },
  {
    schemaName: 'parish_code',
    text: {
      en: 'Parish code',
    }
  },
  {
    schemaName: 'rune_type',
    text: {
      en: 'Rune type',
    }
  },
  {
    schemaName: 'dating',
    text: {
      en: 'Dating period (U, V, or M)',
    }
  },
  {
    schemaName: 'year_from',
    text: {
      en: 'Year from',
    },
  },
  {
    schemaName: 'year_to',
    text: {
      en: 'Year to',
    },
  },
  {
    schemaName: 'style',
    text: {
      en: 'Style',
    }
  },
  {
    schemaName: 'carver',
    text: {
      en: 'Carver',
    }
  },
  {
    schemaName: 'material',
    text: {
      en: 'Material',
    },
  },
  {
    schemaName: 'material_type',
    text: {
      en: 'Material type',
    },
  },
  {
    schemaName: 'objectInfo',
    text: {
      en: 'Object information',
    },
  },
  {
    schemaName: 'references_combined',
    text: {
      en: 'References',
    },
  },
  {
    schemaName: 'additional',
    text: {
      en: 'Other information',
    },
  },
  {
    schemaName: 'normalisation_norse',
    text: {
      en: 'Normalization to Old West Norse',
    },
    css: 'normalization',
    highlight: true,
  },
  {
    schemaName: 'normalisation_scandinavian',
    text: {
      en: 'Normalisation to Old Scandinavian',
    },
    css: 'normalization',
    highlight: true,
  },
  {
    schemaName: 'english_translation',
    text: {
      en: 'Translation to English',
    },
    highlight: true,
  },
  {
    schemaName: 'swedish_translation',
    text: {
      en: 'Translation to Swedish',
    },
    highlight: true,
  },
  {
    schemaName: 'transliteration',
    text: {
      en: 'Transliterated runic text',
    },
    css: 'transliteration',
    highlight: true,
  },
  {
    schemaName: 'num_crosses',
    text: {
      en: 'Number of crosses',
    },
  },
  {
    schemaName: 'cross_form',
    text: {
      en: 'Cross form',
    },
  },
  {
    schemaName: 'images',
    text: {
      en: 'Images',
    }
  },
  {
    schemaName: 'lost',
    text: {
      en: 'Is Lost?',
    }
  }
];

const allButNames = /[\$\[\]\{\}\(\)\?<>\^`´\|¬°·:×¤\+÷']|¶+,\./g;
const punctuation = /[\.,;]/g;

// Two tables below are true for DB 20240910. Assembled manually.
const normalizationWordsToSkip = {
  'U 166': [3, 7],
  'Sm 1': [24, 28],
  'U 637': [10, 12],
  'U 1036': [14, 16],
  'M 11': [16, 35],
  'G 280': [5, 7],
  'GR 56': [8],
  'N KJ72': [22],
  'N B625': [69],
  'N B311': [4],
  'N B265': [25],
  'N B259': [1],
  'N B255': [20],
  'N B27': [3],
  'N A197': [3],
  'N A5': [1],
  'N A144': [1],
  'N 603': [5],
  'N 362': [2],
  'N 208': [8],
  'N 171': [13],
  'N 124': [2],
  'N 114': [3],
  'N 26': [8],
  'N 19': [12],
  'DR NOR2004;7': [18],
  'DR NOR1999;21': [47],
  "G 306": [3],
  "G 129": [11],
  "G 119": [24],
  "Gs 8": [7],
  "Vs 27": [10],
  "Vs 22": [6],
  "Vs 3": [15],
  "U THS10;58": [15],
  "U NOR1998;25": [19],
  "U Fv1976;104": [3],
  "U Fv1953;263": [18],
  "U Fv1948;168": [16],
  "U 1168": [6],
  "U 1162": [11],
  "U 1158": [10],
  "U 1132": [13],
  "U 1111": [11],
  "U 1097": [3],
  "U 1060": [5],
  "U 1042": [10],
  "U 1005": [12],
  "U 968": [3],
  "U 952": [16],
  "U 917": [3],
  "U 896": [10],
  "U 805": [40],
  "U 662": [1],
  "U 618": [12],
  "U 545": [24],
  "U 459": [11],
  "U 423": [11],
  "U 351": [14],
  "Vg 219": [13],
  "Vg 67": [25],
  "Sö Fv1986;218": [8],
  "Sö 344": [3],
  "Sö 320": [5],
  "Sö 256": [10],
  "Sö 205": [3],
  "Sö 130": [20],
  "Sö 109": [13],
  "Sö 105": [5],
  "Sö 82": [9],
  "Sö 46": [19],
  "Sö 21": [6],
  "Ög 180": [4],

};
const transliterationWordsToSkip = {
  "IS IR;166": [12],
  'N 157': [4],
  "DR NOR2002;7": [9],
  "G 325": [8],
  "Nä 20": [6],
  "U Sl115": [1],
  "U Fv1992;156": [7],
  "U Fv1986;84": [1, 14],
  "U 775": [13],
  "U 558": [6],
  "U 431": [12],
  "U 29": [29],
  "Sö 196": [34],
  "Ög 51": [4],
};


let gRenderInProgress = false;
let gMainDisplayScrollTargetId = null;
const NORMALISATION_COLUMNS = new Set(['normalisation_norse', 'normalisation_scandinavian']);
const MAX_VISIBLE_IMAGE_LINKS = 10;

export function setMainDisplayScrollTarget(signatureId) {
  const parsedId = parseInt(signatureId, 10);
  gMainDisplayScrollTargetId = Number.isNaN(parsedId) ? null : parsedId;
}

function scrollMainDisplayToSignature(selectedSignatureIds) {
  const mainDisplay = document.getElementById('mainDisplay');
  if (!mainDisplay) return;

  let targetId = gMainDisplayScrollTargetId;
  if (targetId === null && Array.isArray(selectedSignatureIds) && selectedSignatureIds.length > 0) {
    const fallbackId = parseInt(selectedSignatureIds[selectedSignatureIds.length - 1], 10);
    if (!Number.isNaN(fallbackId)) {
      targetId = fallbackId;
    }
  }
  if (targetId === null) return;

  const targetArticle = mainDisplay.querySelector(`article[rundata-db-id="${targetId}"]`);
  if (!targetArticle) {
    gMainDisplayScrollTargetId = null;
    return;
  }

  const top = Math.max(0, targetArticle.offsetTop - 4);
  mainDisplay.scrollTo({ top, behavior: 'auto' });
  gMainDisplayScrollTargetId = null;
}

function concealPersonalNameMarkersForDisplay(columnName, htmlValue) {
  if (!NORMALISATION_COLUMNS.has(columnName)) {
    return htmlValue;
  }
  return htmlValue.replace(/&quot;/g, '');
}

/**
 * Retrieves a human-readable name for a schema field in the specified language.
 *
 * @param {string} schemaName - The machine name of the schema field.
 * @param {string} [lang='en'] - The language code to get the translation for (defaults to 'en').
 * @returns {string} The translated human-readable name if available, otherwise returns the schemaName.
 */
export function getHumanName(schemaName, lang = 'en') {
  const field = schemaFieldsInfo.find(field => field.schemaName === schemaName);
  if (!field) {
    return schemaName; // Return the schemaName as is if not found
  }
  return field.text[lang] || schemaName; // Return the human name or schemaName if translation is missing
}

// Extracts word boundaries from inscription texts. These texts
// have multiple separators (whitespaces, punctuation) that often
// go together, i.e. space,punctuation,space
// returns array of objects. Each object:
// {start: num, end: num, text: string, isPersonal: 0|1}
// Arguments:
//   str - search string
function getWordBoundaries(str, sourceIsEscaped = false) {
  // regex used to detect word boundaries
  const wordBoundariesSource = "((\\s+|^(·|:|×|¤|'|\\+|÷|¶))(·|:|×|¤|'|\\+|÷|¶){0,1}\\s*)";
  // the reason it is written so complex via | is because we can do html escaping on that string
  const punctuationSource = "(·|:|×|¤|'|\\||\\+|÷|¶|\\(|\\)|\\[|\\])+"
  //const punctuationSource = "([·|:×¤'+÷¶()|[\]\\])+";
  const reg = new RegExp(sourceIsEscaped ? escapeHtml(wordBoundariesSource) : wordBoundariesSource, 'g');
  // regex used to check if detected word is pure punctuation
  const purePunctuation = new RegExp(sourceIsEscaped ? escapeHtml(punctuationSource) : punctuationSource);

  const words = [];
  let wordBegin = 0;

  function processWord(wordBegin, wordEnd) {
    const wordText = str.slice(wordBegin, wordEnd);

    // Skip double sides character
    if (str.slice(wordBegin, wordBegin + 2) === '¶¶') {
      return null;
    }
    // skip {÷
    if (str.slice(wordBegin, wordBegin+2) === "{÷") {
      return null;
    }

    // Check if the word is pure punctuation
    const punctuationCheck = purePunctuation.exec(wordText);
    if (punctuationCheck && punctuationCheck[0].length === wordText.length) {
      return null;
    }

    // skip ^
    if (wordText == "^") {
      return null;
    }


    const oneWord = {
      start: wordBegin,
      end: wordEnd,
      text: wordText,
      isPersonal: 0,
    };

    // Check if the word is personal
    oneWord.isPersonal = isPersonalName(wordText) ? 1 : 0;

    return oneWord;
  }

  let arr;
  while ((arr = reg.exec(str)) !== null) {
    if (wordBegin === arr.index) {
      wordBegin += arr[0].length;
      continue;
    }
    const oneWord = processWord(wordBegin, arr.index);
    if (oneWord) {
      words.push(oneWord);
    }
    wordBegin = arr.index + arr[0].length;
  }

  // Process any remaining text after the last regex match
  if (wordBegin < str.length) {
    const oneWord = processWord(wordBegin, str.length);
    if (oneWord) {
      words.push(oneWord);
    }
  }

  return words;
}

/**
 * Convert a database object to a key map.
 * @param {Object} db - The database object that can be used to run queries.
 * @returns {Object} - The key map object. Key - signature ID, value - all signature info.
 */
export function convertDbToKeyMap(db) {
  let content = db.exec("SELECT all_data.*, signatures_with_aliases.aliases FROM all_data LEFT JOIN signatures_with_aliases ON all_data.signature_id = signatures_with_aliases.signature_id");
  const columns = content[0].columns;
  const allRows = content[0].values;
  const signatureIdColumn = columns.indexOf("signature_id");
  const numCrossesColumn = columns.indexOf("num_crosses");
  const latitudeColumn = columns.indexOf('latitude');
  const longitudeColumn = columns.indexOf('longitude');
  const presentLatitudeColumn = columns.indexOf('present_latitude');
  const presentLongitudeColumn = columns.indexOf('present_longitude');
  const metaColumn = columns.indexOf('id');
  const wordColumns = ['transliteration', 'normalisation_norse', 'normalisation_scandinavian'];
  const crossFormByMetaId = {};

  // Textual cross-form data (used by "Cross form" display field).
  // This view is expected to exist in normal DB builds; if not, we keep it empty.
  try {
    const crossFormContent = db.exec("SELECT meta_id, crosses_textual FROM meta_with_crosses_textual");
    if (crossFormContent.length > 0) {
      crossFormContent[0].values.forEach(([metaId, crossesTextual]) => {
        crossFormByMetaId[metaId] = crossesTextual || "";
      });
    }
  } catch (e) {
    // no-op: leave crossFormByMetaId empty
  }

  const allDbImages = fetchAllImages(db);
  let numDiffers = 0;

  const dbArray = allRows.map(row => {
    let objSignature = {};
    const metaId = row[metaColumn];
    for (let j = 0; j < row.length; j++) {
      const columnName = columns[j];

      objSignature[columnName] = row[j];
      // handle NULL values
      if (row[j] === null) {
        objSignature[columnName] = "";
      }

      /////////////////////////////////////
      // pre-split words and store arrays
      if (wordColumns.includes(columnName)) {
        objSignature[`${columnName}_html`] = escapeHtml(row[j]);
        objSignature[`${columnName}_word_boundaries`] = getWordBoundaries(objSignature[`${columnName}_html`], true);
      }
    }

    // Populate the textual cross form field so "Cross form" can render content.
    objSignature['cross_form'] = crossFormByMetaId[metaId] || "";

    // Build coordination text for main display.
    const hasOriginalCoordinates = objSignature.latitude && objSignature.longitude
      && parseFloat(objSignature.latitude) !== 0 && parseFloat(objSignature.longitude) !== 0;
    const hasCurrentCoordinates = objSignature.present_latitude && objSignature.present_longitude
      && parseFloat(objSignature.present_latitude) !== 0 && parseFloat(objSignature.present_longitude) !== 0;
    const coordinationParts = [];
    if (hasOriginalCoordinates) {
      coordinationParts.push(`Oldest known latitude and longitude: ${objSignature.latitude}, ${objSignature.longitude}`);
    }
    if (hasCurrentCoordinates) {
      coordinationParts.push(`Current latitude and longitude: ${objSignature.present_latitude}, ${objSignature.present_longitude}`);
    }
    objSignature['coordination'] = coordinationParts.join(' | ');

    /////////////////////////////////////////
    // Handle exceptions for word searches

    // special treatment for "Sö 145"
    if (objSignature.signature_text === "Sö 145") {
      // treat `ata i` as a single word
      objSignature['transliteration_html'] = escapeHtml(objSignature.transliteration.replace(": ata i ::", ": ata_i ::"));
      objSignature['transliteration_word_boundaries'] = getWordBoundaries(objSignature['transliteration_html'], true);
      // replace it back
      objSignature['transliteration_word_boundaries'][22].text = 'ata i';
    }
    if (normalizationWordsToSkip.hasOwnProperty(objSignature.signature_text)) {
      const wordsToSkip = normalizationWordsToSkip[objSignature.signature_text];
      objSignature.normalisation_norse_word_boundaries = objSignature.normalisation_norse_word_boundaries.filter((_, i) => !wordsToSkip.includes(i));
      objSignature.normalisation_scandinavian_word_boundaries = objSignature.normalisation_scandinavian_word_boundaries.filter((_, i) => !wordsToSkip.includes(i));
    }
    if (transliterationWordsToSkip.hasOwnProperty(objSignature.signature_text)) {
      const wordsToSkip = transliterationWordsToSkip[objSignature.signature_text];
      objSignature.transliteration_word_boundaries = objSignature.transliteration_word_boundaries.filter((_, i) => !wordsToSkip.includes(i));
    }
    // End of exception handling
    /////////////////////////////////////

    // Adjust small mismatches
    if (objSignature.transliteration_word_boundaries.length == 0 && objSignature.normalisation_norse_word_boundaries.length == 1) {
      if (objSignature.normalisation_norse_word_boundaries[0].text == '...') {
        // reset the normalisation_norse_word_boundaries
        objSignature.normalisation_norse_word_boundaries = [];
        objSignature.normalisation_scandinavian_word_boundaries = [];
      }
    }

    wordColumns.forEach(name => {
      // `${name}_word_boundaries` is a list of objects with keys: start, end, text
      // create a new array out of it with only the text
      objSignature[`${name}_words`] = objSignature[`${name}_word_boundaries`].map(boundary => {
        return boundary.text;
      });
    });
    numDiffers += objSignature.transliteration_word_boundaries.length !== objSignature.normalisation_norse_word_boundaries.length ? 1 : 0;

    objSignature["signature_display"] = prepareSignumForDisplay(objSignature);
    if (objSignature["aliases"]) {
      objSignature["signature_header"] = objSignature["signature_text"] + " (" + objSignature["aliases"] + ")";
    } else {
      objSignature["signature_header"] = objSignature["signature_text"];
    }

    /////////////////////////////////////
    // fill in images
    if (allDbImages.hasOwnProperty(metaId)) {
      const imagesMarkup = makeImagesMarkup(allDbImages[metaId]);
      objSignature["directImages"] = imagesMarkup.directImages;
      objSignature["indirectImages"] = imagesMarkup.indirectImages;
    } else {
      objSignature["directImages"] = "";
      objSignature["indirectImages"] = "";
    }

    /////////////////////////////////////
    // fill in crosses
    let numCrosses = row[numCrossesColumn];
    if (numCrosses > 0) {
      objSignature['crosses'] = crossesForMeta(db, row[metaColumn]);
    } else {
      objSignature['crosses'] = [];
    }

    return objSignature;
  });
  const dbAsJson = new Map();
  dbArray.forEach(inscription => {
    dbAsJson.set(inscription.id, inscription);
  });

  console.log(`Number of signatures with different word boundaries (it should be 0): ${numDiffers}`);

  return dbAsJson;
}

export function prepareSignumForDisplay({signature_text, lost, new_reading}) {
  let additional = "";
  if (lost) {
    additional += "†"
  }
  if (new_reading) {
    additional += "$"
  }
  if (additional.length > 0) {
    additional = " " + additional;
  }

  return signature_text + additional;
}

function resolveUrlOrBlob(urlOrBlob) {
  if (urlOrBlob.startsWith('http://') || urlOrBlob.startsWith('https://')) {
    return urlOrBlob;
  }
  const blobBase = (typeof window !== "undefined" && window.BLOB_BASE_URL)
    ? window.BLOB_BASE_URL
    : "";
  if (blobBase) {
    const normalizedBlobPath = (typeof urlOrBlob.normalize === "function")
      ? urlOrBlob.normalize("NFD")
      : urlOrBlob;
    const encodedBlobPath = normalizedBlobPath
      .split('/')
      .map(part => encodeURIComponent(part))
      .join('/');
    return blobBase.replace(/\/$/, '') + '/' + encodedBlobPath;
  }
  return urlOrBlob;
}

export function fetchAllImages(db) {
  let content = [];
  try {
    content = db.exec("SELECT meta_id, link_url, direct_url, info FROM runes_imagelink");
  } catch (e) {
    // Backwards compatibility with DB snapshots where `info` column is absent.
    content = db.exec("SELECT meta_id, link_url, direct_url FROM runes_imagelink");
  }
  if (!content || content.length === 0) {
    return {};
  }
  const allRows = content[0].values;
  const hasInfoColumn = content[0].columns.includes("info");

  let allImages = {};

  for (let i = 0; i < allRows.length; i++) {
    const row = allRows[i];
    const indirect = row[1] || "";
    const direct = row[2] || "";
    const info = hasInfoColumn ? (row[3] || "") : "";

    const metaId = row[0];
    if (!allImages.hasOwnProperty(metaId)) {
      allImages[metaId] = {links: []};
    }
    allImages[metaId].links.push({indirect, direct, info});
  }
  return allImages;
}

export function makeImagesMarkup(signatureImageLinks) {
  let directImages = "";
  let indirectImages = "";
  const isMobileViewport = isCompactDbLayout();

  const escapeHtml = function (value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  };

  const imageSourceLabel = function (url) {
    try {
      const hostname = (new URL(url)).hostname.replace(/^www\./, "");
      return hostname || url;
    } catch {
      return url;
    }
  };

  const galleryLinks = isMobileViewport
    ? signatureImageLinks.links
    : signatureImageLinks.links.slice(0, MAX_VISIBLE_IMAGE_LINKS);
  const hiddenLinks = isMobileViewport
    ? []
    : signatureImageLinks.links.slice(MAX_VISIBLE_IMAGE_LINKS);

  directImages = '<div class="rundata-image-gallery">';
  galleryLinks.map(function (v) {
    const indirectUrl = escapeHtml(v.indirect);
    const directUrl = escapeHtml(v.direct);
    const sourceLabel = escapeHtml(imageSourceLabel(v.indirect));
    const infoText = (v.info || "").toString().trim();
    const caption = infoText.length > 0
      ? escapeHtml(infoText)
      : `source: <a href="${indirectUrl}" contentEditable="false" target="_blank">${sourceLabel}</a>`;
    const imageContent = (!isMobileViewport || directUrl)
      ? `<img src="${directUrl}" class="rundata-image-avatar" alt="Inscription image">`
      : '<div class="rundata-image-fallback">Open image link</div>';
    directImages += `<figure class="rundata-image-item"><a href="${indirectUrl}" contentEditable="false" target="_blank" class="rundata-image-link">${imageContent}</a><figcaption class="rundata-image-source">${caption}</figcaption></figure>`;
  });
  directImages += '</div>';

  if (!isMobileViewport && hiddenLinks.length > 0) {
    indirectImages = '<details class="rundata-more-image-links"><summary><span class="text-primary text-decoration-underline">Find more image links here</span></summary><ul>';
    hiddenLinks.map(function (v) {
      const indirectUrl = escapeHtml(v.indirect);
      indirectImages += `<li><a href="${indirectUrl}" contentEditable="false" target="_blank">${indirectUrl}</a></li>`;
    });
    indirectImages += '</ul></details>';
  }

  return {directImages, indirectImages};
}

/* Find all crosses related to particular metaId.
 * Returned variable is a multidimensional array. Dimensions:
 * 1. First dimension contains individual crosses.
 * 2. Second dimension denotes cross form group. There could only be 8 groups.
 * 3. Third dimension contains objects with 2 data fields (name, isCertain). Each object represents a particular cross form in a group.
 *    Note that some groups can be empty.
 */
export function crossesForMeta(db, metaId) {
  // we do not check that this meta contains any crosses. This should be done in parent call
  //let cc = db.exec("SELECT id FROM crosses WHERE meta_id = '" + metaId + "'");
  const contents = db.exec("SELECT cross_id, cross_forms.id, cross_forms.name, cross_forms.group_id, cross_definitions.is_certain FROM cross_definitions INNER JOIN cross_forms ON (cross_definitions.form_id = cross_forms.id) WHERE cross_id IN (SELECT id FROM crosses WHERE meta_id = '" + metaId + "') ORDER BY cross_id");
  if (!contents)
    return [];

  let lastCrossId = -1;
  let crosses = [];

  for (let i = 0; i < contents[0].values.length; i++) {
    let crossId = parseInt(contents[0].values[i][0], 10);
    if (crossId != lastCrossId) {
      lastCrossId = crossId;
      crosses.push(Array.apply(null, Array(8)).map(function() {return [];}));
    }

    let formName = contents[0].values[i][2];
    let groupId = contents[0].values[i][3];
    let isCertain = contents[0].values[i][4];

    crosses[crosses.length - 1][parseInt(groupId, 10)].push({name: formName, isCertain: isCertain});
  }
  return crosses;
}

/**
 * Convert list/map of inscriptions to tree nodes suitable for jsTree.
 *
 * @param {*} inscriptions - Either a list of objects or a map. If map is provided, it will be converted to a list of map values.
 */
export function inscriptions2treeNodes(inscriptions) {
  const values = inscriptions instanceof Map ? Array.from(inscriptions.values()) : inscriptions;

  return values.map(inscription => {
    return {
      id: inscription.id.toString(),
      text: inscription.signature_display,
      normalizedText: inscription.signature_text.normalize("NFD").replace(/[\u0300-\u036f]/g, ""),
      icon: false,
      signature: inscription.signature_text,
    };
  });
}

export function selectFirstSignature() {
  let root = $('#jstree').jstree(true).get_node('#');
  $('#jstree').jstree(true).select_node(root.children[0]);
}

/**
 * Selects the inscription in jsTree that corresponds to the map marker that was clicked.
 * This is called by the marker click handler in initMap (index_map.js).
 * Selecting a node triggers the 'changed.jstree' event which calls displaySignatureInfo().
 * @param {string} _signature - Kept for API compatibility with index_map.js call site; not used here
 * @param {number|string} inscriptionId - The DB id of the inscription to select
 */
export function scrollToInscription(_signature, inscriptionId) {
  const tree = $('#jstree').jstree(true);
  tree.deselect_all();
  tree.select_node(String(inscriptionId));
  const container = $('#jstree')[0];
  const el = document.getElementById(`${inscriptionId}_anchor`);
  if (el && container) {
    const containerRect = container.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();
    container.scrollTop = container.scrollTop + elRect.top - containerRect.top;
  }
}

/**
 * Convert list of inscriptions to a list of select options in html format.
 */
export function inscriptions2Select(container, dbMap) {
  // clear container
  container.innerHTML = "";

  dbMap.forEach((inscription, id) => {
    const option = document.createElement("option");
    option.value = id;
    option.text = inscription.signature_display;

    container.appendChild(option);
  });
}

/**
 * Show tooltip message on a DOM element.
 *
 * @param {object} el DOM element, e.g. document.getElementById("myBtn")
 * @param {string} message Tooltip message
 */
function setTooltip(el, message) {
  const that = $(el);
  that.attr('data-bs-title', message).tooltip('show');
  // do not care about multiple calls to setTimeout
  setTimeout(function() {
    that.tooltip('hide');
  }, 900);
}

export function initClipboardButtons() {
  /**
   * There is a collection of buttons that represent various tricky symbols, like umlauts.
   * Clicking on them should copy the relevant symbol to the clipboard.
   */
  const clipboardButtons = document.querySelectorAll('.clip');
  clipboardButtons.forEach(button => {
    button.addEventListener('click', function() {
      const symbol = button.innerText;
      navigator.clipboard.writeText(symbol).then(function() {
        setTooltip(button, 'Copied to clipboard!');
      }).catch(function(err) {
        setTooltip(button, 'Failed to copy!');
      });
    });
  });
}

export function arraysEqual(a, b) {
  if (a === b) return true;
  if (a == null || b == null) return false;
  if (a.length != b.length) return false;

  for (var i = 0; i < a.length; ++i) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

export function displaySignatureInfo() {
  const indices = $('#jstree').jstree(true).get_selected();
  if (indices.length == 0) {
    return;
  }

  if (gRenderInProgress) {
    gRenderInProgress = false;
    setTimeout(displaySignatureInfo, 300);
    return;
  }
  document.getElementById('mainDisplay').innerHTML = "<img src='https://cdnjs.cloudflare.com/ajax/libs/jstree/3.3.7/themes/default-dark/throbber.gif'><br>";
  gRenderInProgress = true;
  setTimeout(renderSignatures, 100);
}

function renderSignatures() {
  if (!gRenderInProgress)
    return;

  try {
    const selectedSignatureIds = $('#jstree').jstree(true).get_selected();
    // When a search is active, render all active search hits in the main window.
    // This ensures users can inspect the full result set without selecting each ID.
    const selectedSignatures = (gViewModel && gViewModel.searchResults !== null)
      ? gViewModel.getActiveInscriptions()
      : gViewModel.getInscriptions(selectedSignatureIds);

    const html = inscriptions2markup(selectedSignatures);
    document.getElementById('mainDisplay').innerHTML = html.join('');
    scrollMainDisplayToSignature(selectedSignatureIds);
  } catch (e) {
    console.error(`Error rendering signatures: ${e}`);
  } finally {
    gRenderInProgress = false;
  }
}

function escapeHtml(string) {
  const entityMap = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    '/': '&#x2F;',
    '`': '&#x60;',
    '=': '&#x3D;'
  };

  return String(string).replace(/[&<>"'`=\/]/g, function (s) {
    return entityMap[s];
  });
}

/**
 * Replace specific raw URLs inside a plain-text reference with labelled
 * anchors, preserving surrounding citation text.
 *
 * Current mappings:
 * - http://fornvannen.se/... -> "Fornvännen PDF"
 * - http://kulturarvsdata.se/raa/samla/html/<number> -> "ATA Rapport"
 *
 * Returns null when no matching URL is found.
 */
function renderSpecialReferenceLinks(refText) {
  const raw = String(refText || '');
  const urlRules = [
    {
      regex: /http:\/\/fornvannen\.se\/[^\s;|]+/gi,
      label: 'Fornvännen PDF',
    },
    {
      regex: /http:\/\/kulturarvsdata\.se\/raa\/samla\/html\/\d+/gi,
      label: 'ATA Rapport',
    },
  ];
  const matches = [];
  urlRules.forEach(rule => {
    for (const match of raw.matchAll(rule.regex)) {
      const start = match.index ?? -1;
      if (start < 0) {
        continue;
      }
      matches.push({
        start,
        end: start + match[0].length,
        fullUrl: match[0],
        label: rule.label,
      });
    }
  });

  if (matches.length === 0) {
    return null;
  }
  matches.sort((a, b) => (a.start - b.start) || (b.end - a.end));

  let result = '';
  let lastIndex = 0;
  for (const match of matches) {
    if (match.start < lastIndex) {
      // Skip overlaps, keeping the earliest non-overlapping match.
      continue;
    }
    const fullUrl = match.fullUrl;
    const cleanUrl = fullUrl.replace(/[),.;]+$/, '');
    const trailing = fullUrl.slice(cleanUrl.length);

    result += escapeHtml(raw.slice(lastIndex, match.start));
    result += `<a href="${escapeHtml(cleanUrl)}" target="_blank" contenteditable="false">${escapeHtml(match.label)}</a>`;
    result += escapeHtml(trailing);
    lastIndex = match.end;
  }

  result += escapeHtml(raw.slice(lastIndex));
  return result;
}

/**
 * Highlight whole words in a string given their pre-computed character
 * boundaries. Used for word-aligned fields (transliteration and the two
 * normalisations). The boundaries are sorted in-place before rendering.
 *
 * @param {string} str - The (already HTML-escaped) string to render.
 * @param {Array<{start: number, end: number, text: string}>} wordBoundaries
 * @returns {string} The string with matched words wrapped in highlight spans.
 */
export function highlightWordsFromWordBoundaries(str, wordBoundaries) {
  // Sort the indices to ensure they are processed in the correct order
  wordBoundaries.sort((a, b) => a.start - b.start);

  let highlightedStr = '';
  let lastIndex = 0;

  wordBoundaries.forEach(({start, end, text}) => {
    // Append the part of the string before the current word
    highlightedStr += str.slice(lastIndex, start);
    // Wrap the word in a <span> tag and append it
    highlightedStr += `<span class="highlight">${str.slice(start, end)}</span>`;
    // Update the lastIndex to the end of the current word
    lastIndex = end;
  });

  // Append the remaining part of the string after the last word
  highlightedStr += str.slice(lastIndex);

  return highlightedStr;
}

/**
 * Highlight substring ranges in a raw (un-escaped) string, producing an
 * HTML-safe string with `<span class="highlight">...</span>` around each
 * matched range. Non-highlight text is HTML-escaped via `escapeHtml`;
 * highlight content is also escaped before being wrapped.
 *
 * @param {string} rawStr - Original (un-escaped) field value.
 * @param {Array<[number, number]>} ranges - Array of [start, end) pairs into `rawStr`.
 * @returns {string} HTML-safe string with highlights applied.
 */
export function highlightSubstringRanges(rawStr, ranges) {
  const str = rawStr == null ? '' : String(rawStr);
  if (!Array.isArray(ranges) || ranges.length === 0) {
    return escapeHtml(str);
  }
  // Sort and merge overlapping/adjacent ranges.
  const sorted = ranges
    .map(([s, e]) => [Math.max(0, s|0), Math.min(str.length, e|0)])
    .filter(([s, e]) => e > s)
    .sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [s, e] of sorted) {
    if (merged.length && s <= merged[merged.length - 1][1]) {
      merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], e);
    } else {
      merged.push([s, e]);
    }
  }

  let out = '';
  let last = 0;
  for (const [s, e] of merged) {
    if (s > last) out += escapeHtml(str.slice(last, s));
    out += `<span class="highlight">${escapeHtml(str.slice(s, e))}</span>`;
    last = e;
  }
  if (last < str.length) out += escapeHtml(str.slice(last));
  return out;
}

export function inscriptions2markup(inscriptions) {
  // array of selected inscription IDs
  //const selectedSignatureIds = $('#jstree').jstree(true).get_selected();
  const lang = 'en';
  const paragraphSymbol = '§';
  const sidesHeader = "Sides or/and reading variants:"

  const showHeaders = $('#chkDisplayHeaders').is(":checked");
  const userSelectedFields =  getUserSelectedFields();
  const isMobileViewport = isCompactDbLayout();
  let markupData = [];
  for (let i = 0; i < inscriptions.length; i++) {

    const inscriptionData = inscriptions[i];
    const signatureId = inscriptionData.id;
    const signatureName = inscriptionData.signature_text;

    let paragraph = `<article signature="${signatureName}" id="${signatureName}" rundata-db-id="${signatureId}" class="inscription-section">`;
    for (let j = 0; j < userSelectedFields.length; j++) {
      const field = userSelectedFields[j];
      const columnName = field.schemaName == "signature_text" ? "signature_header" : field.schemaName;
      const humanName = field.text[lang];
      const cssStyle = field.css || "";
      const shouldHighlight = field.highlight || false;

      let columnData = "";
      if (columnName in inscriptionData) {
        columnData = inscriptionData[columnName].toString();
      }
      const trimmedColumnData = String(columnData || '').trim();
      if (isMobileViewport) {
        if (columnName === 'lost' && (trimmedColumnData === '' || trimmedColumnData === '0' || trimmedColumnData.toLowerCase() === 'false')) {
          continue;
        }
        if (columnName === 'num_crosses' && (trimmedColumnData === '' || trimmedColumnData === '0')) {
          continue;
        }
        if (columnName === 'rune_type' && trimmedColumnData === '') {
          continue;
        }
        if (columnName === 'cross_form' && trimmedColumnData === '' && inscriptionData['num_crosses'] == 0) {
          continue;
        }
      }
      if (showHeaders) {
        paragraph += `<h4>${humanName}</h4>`;
      } else if (paragraph.length > 0 && columnData !== "") {
        // only add if there is some content to show and this is not the first field. Otherwise, we do not want to have empty lines in the beginning of the inscription info.
        if (paragraph.slice(-7) === "</span>") {
          paragraph += "<br>";
        }
      }

      // Smiley is a special symbol: word substitute when word is not present
      // We do not need to show it.
      columnData = columnData.replace(/ ☺ /g, ' ');

      if (columnName === 'images') {
        if (!showHeaders && (inscriptionData['directImages'].length == 0 && inscriptionData['indirectImages'].length == 0)) {
          // early stop if no headers and no images
          continue;
        }
        if (inscriptionData['directImages'].length > 0) {
          paragraph += inscriptionData['directImages'];
          if (inscriptionData['indirectImages'].length > 0) {
            // add image links as they have not been added yet
            paragraph += '<br>' + inscriptionData['indirectImages'];
          }
          continue;
        }
        if (inscriptionData['indirectImages'].length > 0) {
          paragraph += inscriptionData['indirectImages'];
          continue;
        }
        if (showHeaders) {
          paragraph += '<i>No images.</i>';
        }

        continue;
      }

      if (columnName === "cross_form") {
        const hasCrossText = !!(columnData && columnData.trim() !== '');
        if (!hasCrossText && inscriptionData['num_crosses'] == 0) {
          if (showHeaders) {
            paragraph += '<i>No crosses.</i>';
          }
          continue;
        }

        if (hasCrossText) {
          paragraph += `<span class="${cssStyle}">${escapeHtml(columnData)}</span>`;
          paragraph += '<br>';
        }

        paragraph += '<table class="crosses" border="1">';
        paragraph += '<thead><tr>';
        paragraph += '<th>A</th>';
        paragraph += '<th>B</th>';
        paragraph += '<th>C</th>';
        paragraph += '<th>D</th>';
        paragraph += '<th>E</th>';
        paragraph += '<th>F</th>';
        paragraph += '<th>G</th>';
        paragraph += '</th></thead>';
        paragraph += '<tbody>';

        const allCrosses = inscriptionData['crosses'];
        for (let k = 0; k < allCrosses.length; k++) {
          if (allCrosses[k][0].length > 0) {
            // this is a cross from an undefined group
            paragraph += '<tr><td colspan="7">' + allCrosses[k][0][0].name + '</td></tr>';
            continue;
          }
          paragraph += '<tr>';
          // we have 8 groups in total, 0 being free-text and not a real group
          for (let gr = 1; gr < 8; gr++) {
            if (allCrosses[k][gr].length == 0) {
              paragraph += '<td><span class="null">&#8709;</span></td>';
              continue;
            }
            paragraph += '<td>';
            paragraph += allCrosses[k][gr].map(function (v, i) {
              let res = '<img src="' + getCrossUrl(v.name) + '" alt="'+v.name+'" title="'+v.name+'" width="32" height="32">';
              if (v.isCerain == 0) {
                res += '?';
              }
              return res;
            }).join(', ');
            paragraph += '</td>';
          }
        }
        paragraph += '</tbody></table>';
        continue;
      }

      if (columnName === "coordination") {
        const lines = columnData
          .split('|')
          .map(item => item.trim())
          .filter(item => item.length > 0);

        if (lines.length === 0) {
          if (showHeaders) {
            paragraph += '<i>Absent, not in the database.</i>';
          }
          continue;
        }

        paragraph += `<span class="${cssStyle}">${lines.map(line => escapeHtml(line)).join('<br>')}</span>`;
        continue;
      }

      if ((columnData == '' || columnData == null) && showHeaders) {
        paragraph += '<i>Absent, not in the database.</i>';
        continue;
      }

      if (columnName == "references_combined") {
        if (columnData && columnData.trim() !== '') {
          const refs = columnData.split('|').map(r => r.trim()).filter(r => r.length > 0);
          if (refs.length > 0) {
            paragraph += `<ul class="${cssStyle}">`;
            refs.forEach(ref => {
              const sep = ref.indexOf(':::');
              if (sep !== -1) {
                // Encoded link: "<label>:::<url-or-blob-filename>"
                const label = ref.substring(0, sep);
                const urlOrBlob = ref.substring(sep + 3);
                const url = resolveUrlOrBlob(urlOrBlob);
                paragraph += `<li><a href="${url}" target="_blank" contenteditable="false">${escapeHtml(label)}</a></li>`;
              } else {
                const specialLinksMarkup = renderSpecialReferenceLinks(ref);
                if (specialLinksMarkup !== null) {
                  paragraph += `<li>${specialLinksMarkup}</li>`;
                  return;
                }
                if (ref.includes('https://')) {
                // Legacy unencoded URL (no label stored)
                  paragraph += `<li><a href="${ref}" target="_blank" contenteditable="false">${ref}</a></li>`;
                } else {
                  paragraph += `<li>${escapeHtml(ref)}</li>`;
                }
              }
            });
            paragraph += '</ul>';
          } else if (showHeaders) {
            paragraph += '<i>Absent, not in the database.</i>';
          }
        } else if (showHeaders) {
          paragraph += '<i>Absent, not in the database.</i>';
        }
        continue;
      }

      const fieldRanges = inscriptionData.matchDetails
        && inscriptionData.matchDetails.fieldRanges
        && inscriptionData.matchDetails.fieldRanges[columnName];
      if (shouldHighlight && Array.isArray(fieldRanges) && fieldRanges.length > 0) {
        // Highlight ranges in the raw string, then escape non-highlight segments.
        columnData = highlightSubstringRanges(columnData, fieldRanges);
      } else {
        columnData = escapeHtml(columnData);

        if (shouldHighlight && inscriptionData.hasOwnProperty('matchDetails') && inscriptionData.matchDetails !== null && inscriptionData.matchDetails.hasOwnProperty('wordIndices')) {
          const entryWordBoundaries = inscriptionData[`${columnName}_word_boundaries`];
          // Word-indices highlighting only applies to columns that were pre-split into
          // word boundaries (transliteration / normalisation_*). Translation columns
          // are also `highlight: true` but have no `_word_boundaries`, so skip them
          // to avoid TypeError on undefined.filter (see issue: normalization search
          // crash "can't access property 'filter', e is undefined").
          if (Array.isArray(entryWordBoundaries)) {
            const matchedWords = inscriptionData.matchDetails.wordIndices;
            const matchedWordBoundaries = entryWordBoundaries.filter((_, i) => matchedWords.includes(i));
            columnData = highlightWordsFromWordBoundaries(columnData, matchedWordBoundaries);
          }
        }
      }

      // Keep personal-name markers in DB/search data, but hide them in
      // rendered normalisation text shown in the main window.
      columnData = concealPersonalNameMarkersForDisplay(columnName, columnData);

      if (columnData.indexOf(paragraphSymbol) !== -1) {
        const parts = columnData.split(paragraphSymbol);
        paragraph += sidesHeader + "<ul>";
        parts.forEach(part => {
          if (!part.trim()) {
            return;
          }

          paragraph += `<li><span class="${cssStyle}">${paragraphSymbol} ${part}</span></li>`;
        });
        paragraph += "</ul>";
      } else {
        paragraph += `<span class="${cssStyle}">${columnData}</span>`;
      }
    }
    paragraph += '</article>';
    markupData.push(paragraph);
  }
  return markupData;
}

/**
 * Handle message from export worker
 */
export function onExportWorkerMessage(e) {
  gExportInProgress = false;

  if (e.data.error) {
    onExportError({message: e.data.message});
    return;
  }

  try {
    // Create a download for the XLSX file
    if (e.data.buffer) {
      // Convert ArrayBuffer to Blob with the correct MIME type
      const blob = new Blob([e.data.buffer], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });

      // Create a download link and trigger the download
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'rundata-net_results.xlsx';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Close the modal after successful export
      closeResultsIoModal();
    }
  } catch (error) {
    onExportError(error);
  } finally {
    hideLoading();
  }
}

/**
 * Handle export errors
 */
export function onExportError(error) {
  console.error('Export error:', error);
  hideLoading();
  gExportInProgress = false;

  // Display error to user
  showAlert("Export error: " + (error.message || 'Unknown error'));
}

export function showAlert(message) {
  const alertObj = document.getElementById('alertObj');
  alertObj.textContent = message;
  alertObj.style.display = 'block';

  // Hide the alert after 5 seconds
  setTimeout(() => {
    alertObj.style.display = 'none';
  }, 5000);
}

/**
 * Helper function to show loading indicator
 * @param {string} [description] - Optional loading description text
 */
export function showLoading(description) {
  const defaultDescription = "It can take up to a minute.";
  const txtLoadingDescription = document.getElementById('txtLoadingDescription');

  if (txtLoadingDescription) {
    txtLoadingDescription.textContent = description || defaultDescription;
  }
  $('#loading').show();
}

/**
 * Helper function to hide loading indicator
 */
export function hideLoading() {
  $('#loading').hide();
}

export function closeResultsIoModal() {
  $('#modalResultsIo').modal('hide');
}
