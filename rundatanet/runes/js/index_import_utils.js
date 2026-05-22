function handleImportWrapper(evt) {
  handleFiles(evt.target.files);
  closeResultsIoModal();

  // reset form, so that we can import the same file again if we need to
  $('form#form-signature-import').get(0).reset();
}

function handleFiles(files) {
  if (files.length == 0) {
    return;
  }
  var fileReader = new FileReader();
  var file = files[0]; // be sure to take just a single file
  const isExcelImport = isExcelFile(file);
  fileReader.onloadend = function(evt) {
    if (evt.target.readyState == FileReader.DONE) {
      $('#loading-sub-text').html('This dialog will disappear once data is ready');
      showLoading();
      if (isExcelImport) {
        setTimeout(importSignaturesFromExcel, 10, evt.target.result);
      } else {
        setTimeout(importSignaturesFromText, 10, evt.target.result);
      }
    }
  }
  if (isExcelImport) {
    fileReader.readAsArrayBuffer(file);
  } else {
    fileReader.readAsText(file);
  }
}

function handleDrop(e) {
  let dt = e.dataTransfer;
  let files = dt.files;

  handleFiles(files);
  closeResultsIoModal();
}

// Event handler that stops event propagation. Used for drag and drop support
function preventDefaults (e) {
  e.preventDefault()
  e.stopPropagation()
}
function highlight(e) {
  dropArea.classList.add('highlight')
}

function unhighlight(e) {
  dropArea.classList.remove('highlight')
}

// Import list of signatures provided from a file
// Function argument fileContent is the actual file content.
function importSignaturesFromText(fileContent) {
  if (fileContent === null) {
    return;
  }
  if (/[\x00-\x08\x0E-\x1F]/.test(fileContent)) {
    alert("Seems like the file you've selected is not textual. Please select a different file.");
    hideLoading();
    return;
  }

  const csvData = Papa.parse(fileContent);
  const values = extractValuesFromRows(csvData.data);
  applyImportedSignatures(values);
}

function importSignaturesFromExcel(arrayBuffer) {
  if (typeof XLSX === 'undefined') {
    alert('Excel import is not available right now. Please try CSV/TXT format.');
    hideLoading();
    return;
  }
  if (arrayBuffer === null) {
    return;
  }

  try {
    const workbook = readWorkbookWithFallbacks(arrayBuffer);
    if (!workbook.SheetNames || workbook.SheetNames.length === 0) {
      alert('No worksheet found in this Excel file.');
      hideLoading();
      return;
    }
    let values = [];
    for (const sheetName of workbook.SheetNames) {
      const currentSheet = workbook.Sheets[sheetName];
      const rows = XLSX.utils.sheet_to_json(currentSheet, {
        header: 1,
        raw: false,
        defval: '',
      });
      values = extractValuesFromRows(rows);
      if (values.length > 0) {
        break;
      }
    }
    applyImportedSignatures(values);
  } catch (error) {
    console.error('Failed to parse Excel import', error);
    alert(`Could not read this Excel file. Please check the file and try again.\n\nDetails: ${formatImportError(error)}`);
    hideLoading();
  }
}

function readWorkbookWithFallbacks(arrayBuffer) {
  const uint8 = new Uint8Array(arrayBuffer);
  const readers = [
    { label: 'array/uint8', fn: () => XLSX.read(uint8, { type: 'array' }) },
    { label: 'array/arrayBuffer', fn: () => XLSX.read(arrayBuffer, { type: 'array' }) },
    { label: 'buffer/uint8', fn: () => XLSX.read(uint8, { type: 'buffer' }) },
    {
      label: 'binary-string',
      fn: () => {
        const binary = arrayBufferToBinaryString(arrayBuffer);
        return XLSX.read(binary, { type: 'binary' });
      },
    },
    {
      label: 'base64',
      fn: () => {
        const base64 = arrayBufferToBase64(arrayBuffer);
        return XLSX.read(base64, { type: 'base64' });
      },
    },
  ];

  const failures = [];
  for (const reader of readers) {
    try {
      return reader.fn();
    } catch (error) {
      failures.push(`[${reader.label}] ${formatImportError(error)}`);
    }
  }
  throw new Error(`Unable to parse workbook. Tried: ${failures.join(' | ')}`);
}

function arrayBufferToBinaryString(arrayBuffer) {
  const bytes = new Uint8Array(arrayBuffer);
  const chunkSize = 0x8000;
  let binary = '';
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode.apply(null, chunk);
  }
  return binary;
}

function arrayBufferToBase64(arrayBuffer) {
  return btoa(arrayBufferToBinaryString(arrayBuffer));
}

function formatImportError(error) {
  if (!error) {
    return 'Unknown error';
  }
  if (typeof error === 'string') {
    return error;
  }
  if (error.message) {
    return error.message;
  }
  try {
    return JSON.stringify(error);
  } catch (_) {
    return String(error);
  }
}

function applyImportedSignatures(values) {
  if (!values || values.length === 0) {
    alert('No signatures or IDs were found in the imported file.');
    hideLoading();
    return;
  }
  const uniqueValues = [...new Set(values)];
  const joinedValues = uniqueValues.join('|');

  var rule = [{
    id: "inscription_id",
    field: "signature_text",
    type: "string",
    input: "text",
    operator: "in_separated_list",
    value: joinedValues,
    ignoreCase: false,
  }];

  var allRules = {
    condition: 'OR',
    rules: rule,
    not: false,
  };

  $(`#${inpQueryBuilder}`).queryBuilder('setRules', allRules, true);
  // doSearch();
  hideLoading();
  // After importing signatures, automatically trigger the search
  document.getElementById('btnSearch').click();
}

function normalizeCellValue(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value).trim();
}

function extractValuesFromRows(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return [];
  }

  const headerCandidates = new Set(['signature', 'signature_text', 'id', 'inscription_id']);
  const firstRow = Array.isArray(rows[0]) ? rows[0] : [rows[0]];
  let signatureColumn = 0;
  let firstDataRow = 0;

  const headerIndex = firstRow.findIndex(item => headerCandidates.has(normalizeCellValue(item).toLowerCase()));
  if (headerIndex !== -1) {
    signatureColumn = headerIndex;
    firstDataRow = 1;
  }

  const values = [];
  for (let i = firstDataRow; i < rows.length; i++) {
    const row = Array.isArray(rows[i]) ? rows[i] : [rows[i]];
    const candidate = normalizeCellValue(row[signatureColumn]);
    if (candidate.length === 0) {
      continue;
    }
    values.push(candidate);
  }

  return values;
}

function isExcelFile(file) {
  const excelExtPattern = /\.(xlsx|xls|xlsm|xlsb|ods)$/i;
  if (file && file.name && excelExtPattern.test(file.name)) {
    return true;
  }
  const mime = (file && file.type) ? file.type : '';
  return mime.includes('spreadsheetml') || mime.includes('ms-excel') || mime.includes('opendocument.spreadsheet');
}

export function initDragAndDrop() {
  const dropArea = document.getElementById('drop-area');
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false)
  });
  ['dragenter', 'dragover'].forEach(eventName => {
    dropArea.addEventListener(eventName, highlight, false)
  });
  ['dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, unhighlight, false)
  });
  dropArea.addEventListener('drop', handleDrop, false);
  document.getElementById('fileElem').addEventListener('change', handleImportWrapper, false);
}
