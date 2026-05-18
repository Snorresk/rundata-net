/**
 * Web Worker for exporting inscription data to Excel format
 *
 * Input: e.data is a dictionary with fields:
 *   inscriptions - Array of inscription objects from gViewModel.getActiveInscriptions()
 *   columns - Object mapping column names to human-readable names
 *   rules - Optional. Search parameters to include in a separate sheet
 *
 * Creates and downloads an XLSX file
 */

// Import the XLSX library
importScripts('https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js');

onmessage = function(e) {
  try {
    const inscriptions = e.data.inscriptions;
    const columnMap = e.data.columnMap;
    const rules = e.data.rules; // Optional search parameters

    // Extract column names and human names from the column map
    const columns = Object.keys(columnMap);
    const humanNames = columns.map(col => columnMap[col]);

    // Process the data and generate Excel data
    const processedData = processDataForExcel(inscriptions, columns);

    // Create workbook and main worksheet
    const workbook = XLSX.utils.book_new();
    const worksheet = XLSX.utils.aoa_to_sheet([
      humanNames, // Header row with human-readable column names
      ...processedData
    ]);

    // Add the main data worksheet
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Results');

    // If search rules are provided, add them to a separate sheet
    if (rules && !isEmpty(rules)) {
      const rulesSheet = createRulesWorksheet(rules);
      XLSX.utils.book_append_sheet(workbook, rulesSheet, 'Search Parameters');
    }

    // Generate the XLSX file as an ArrayBuffer
    const excelBuffer = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' });

    // Send the processed data back to the main thread
    postMessage({
      buffer: excelBuffer,
      success: true
    });
  } catch (error) {
    console.error('Error in export worker:', error);
    postMessage({
      error: true,
      message: error.message,
      stack: error.stack
    });
  }
};

/**
 * Process inscription data for Excel export
 *
 * @param {Array} inscriptions - Array of inscription objects
 * @param {Array} columns - Array of column names to include
 * @returns {Array} Array of arrays with processed data
 */
function processDataForExcel(inscriptions, columns) {
  const result = [];

  for (let i = 0; i < inscriptions.length; i++) {
    const rowData = [];
    const inscription = inscriptions[i];

    if (!inscription) {
      console.error(`No data found for inscription at index: ${i}`);
      continue;
    }

    for (let j = 0; j < columns.length; j++) {
      const columnName = columns[j];
      let colData = inscription[columnName];

      // Coordinates in export should be two dedicated columns with plain values.
      if (columnName === 'latitude') {
        colData = formatCoordinates(inscription.latitude, inscription.longitude);
      } else if (columnName === 'present_latitude') {
        colData = formatCoordinates(inscription.present_latitude, inscription.present_longitude);
      }

      // Special handling for null values
      if (colData === null || colData === undefined) {
        colData = '';
      }

      // Special handling for signature_text
      if (columnName === 'signature_text' && inscription.hasOwnProperty('signature_text_raw')) {
        colData = inscription['signature_text_raw'];
      }

      // Special handling for crosses
      if (columnName === 'crosses') {
        colData = processCrosses(inscription[columnName]);
      }

      // Strip label:::url encoding in references for clean flat text in Excel
      if (columnName === 'references_combined' && typeof colData === 'string') {
        colData = colData.split(' | ').map(ref => {
          const sep = ref.indexOf(':::');
          return sep !== -1 ? ref.substring(0, sep) + ': ' + ref.substring(sep + 3) : ref;
        }).join(' | ');
      }

      // Convert arrays to strings
      if (Array.isArray(colData)) {
        colData = colData.join(';');
      }

      rowData.push(colData);
    }

    result.push(rowData);
  }

  return result;
}

function formatCoordinates(latitude, longitude) {
  const lat = Number(latitude);
  const lon = Number(longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat === 0 || lon === 0) {
    return '';
  }
  return `${latitude}, ${longitude}`;
}

/**
 * Process cross data for Excel format
 *
 * @param {Array} crosses - Array of cross data
 * @returns {String} Formatted cross data as string
 */
function processCrosses(crosses) {
  if (!crosses || crosses.length === 0) {
    return '';
  }

  const crossData = [];

  for (let cId = 0; cId < crosses.length; cId++) {
    const crossObj = crosses[cId];
    const oneCross = [];

    if (crossObj[0] && crossObj[0].length > 0) {
      // This cross has something in group 0, so it must not contain anything in other groups
      crossData.push(crossObj[0][0].name);
      continue;
    }

    // Process each group
    for (let gId = 1; gId < crossObj.length; gId++) {
      const groupItems = crossObj[gId];

      if (!groupItems || groupItems.length === 0) {
        oneCross.push('');
        continue;
      }

      const oneGroup = [];
      for (let fId = 0; fId < groupItems.length; fId++) {
        const crossForm = groupItems[fId];
        if (crossForm.isCertain) {
          oneGroup.push(crossForm.name);
        } else {
          oneGroup.push(`${crossForm.name} ?`);
        }
      }

      oneCross.push(oneGroup.join(',')); // Join individual cross forms with comma
    }

    crossData.push(oneCross.join(';')); // Join groups with semicolon
  }

  return crossData.join(' & '); // Join crosses with ampersand
}

/**
 * Create a worksheet for search rules
 *
 * @param {Object} rules - Query builder rules object
 * @returns {Object} XLSX worksheet
 */
function createRulesWorksheet(rules) {
  // Convert the rules object to a readable format
  const rulesData = [];
  const rulesString = JSON.stringify(rules, null, 2);

  // Add title row
  rulesData.push(['Search Parameters']);
  rulesData.push(['Generated on', new Date().toLocaleString()]);
  rulesData.push(['']); // Empty row for spacing
  rulesData.push([rulesString]);

  return XLSX.utils.aoa_to_sheet(rulesData);
}

/**
 * Check if an object is empty
 *
 * @param {Object} obj - Object to check
 * @returns {boolean} True if object is empty, false otherwise
 */
function isEmpty(obj) {
  return Object.keys(obj).length === 0;
}
