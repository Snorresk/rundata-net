(function () {
  'use strict';

  /**
   * Shared search helpers used by both the main index page and the EDA page.
   */

  /**
   * Checks if a given word is a personal name.
   * @param {string} word - The word to check.
   * @returns {boolean} - True if the word is a personal name, false otherwise.
   */
  function isPersonalName(word) {
    return word.startsWith('"') || word.startsWith('&quot;')
      || word.includes('/"') || word.includes('/&quot;');
  }

  /**
   * Normalizes whitespace in a string by replacing all whitespace characters
   * with regular spaces.
   *
   * @param {*} value - The value to normalize
   * @returns {string} The normalized string
   */
  function normalizeWhitespace(value) {
    return String(value).replace(/\s/g, ' ');
  }

  /**
   * Prepares a string for comparison by normalizing whitespace and optionally lowercasing.
   * @param {*} value - The value to prepare
   * @param {boolean} ignoreCase - Whether to lowercase the string
   * @returns {string} The prepared string
   */
  function prepareForComparison(value, ignoreCase) {
    const normalizedValue = normalizeWhitespace(value);
    return ignoreCase ? normalizedValue.toLowerCase() : normalizedValue;
  }

  /**
   * Strips editorial special symbols from a string so that searches can match
   * text regardless of annotation markers.
   *
   * Handles both literal characters and HTML-entity forms.
   *
   * @param {string} str - The string to strip
   * @returns {string} The string with special symbols removed
   */
  function stripSpecialSymbols(str) {
    return String(str)
      .replace(/&quot;/g, '')
      .replace(/&lt;/g, '')
      .replace(/&gt;/g, '')
      .replace(/["<>|[\](){}^\u00b4?+:\u00d7\u00b7\u00a4'÷¶]/g, '');
  }

  /**
   * Returns a word search function based on the specified search mode.
   * @param {string} searchMode - The search mode ('exact', 'beginsWith', 'endsWith', 'regex', 'includes', 'contains'). 'contains' is an alias for 'includes'.
   * @param {Object} options - Additional options
   * @param {boolean} [options.ignoreCase=false] - Whether to ignore case when searching
   * @param {boolean} [options.includeSpecialSymbols=false] - Whether to keep editorial symbols in comparisons
   * @returns {Function} A search function that takes (word, query) parameters
   * @throws {Error} When an invalid regex pattern is provided in regex mode
   */
  function getWordSearchFunction(searchMode, options = {}) {
    const { ignoreCase = false, includeSpecialSymbols = false } = options;
    const normalizedSearchMode = searchMode === 'contains' ? 'includes' : searchMode;

    const prepareString = (str) => {
      let preparedValue = prepareForComparison(str, ignoreCase);
      if (!includeSpecialSymbols) {
        preparedValue = stripSpecialSymbols(preparedValue);
      }
      return preparedValue;
    };

    const prepareWord = (word) => {
      if (word.includes('&#x2F;') || word.includes('/')) {
        return word.split(/&#x2F;|\//).map(name => {
          return name.trim().replace(/^(&quot;|")/, '');
        });
      }

      return [word];
    };

    switch (normalizedSearchMode) {
      case 'exact':
        return (word, query) => {
          const words = prepareWord(word);
          return words.some(oneWord => prepareString(oneWord) === prepareString(query));
        };

      case 'beginsWith':
        return (word, query) => {
          const words = prepareWord(word);
          return words.some(oneWord => prepareString(oneWord).startsWith(prepareString(query)));
        };

      case 'endsWith':
        return (word, query) => {
          const words = prepareWord(word);
          return words.some(oneWord => prepareString(oneWord).endsWith(prepareString(query)));
        };

      case 'regex':
        return (word, query) => {
          try {
            const flags = ignoreCase ? 'i' : '';
            const regex = new RegExp(query, flags);
            return regex.test(word);
          } catch (error) {
            throw new Error(`Invalid regex pattern: ${query}`);
          }
        };

      case 'includes':
      default:
        return (word, query) => {
          const words = prepareWord(word);
          return words.some(oneWord => prepareString(oneWord).includes(prepareString(query)));
        };
    }
  }

  /**
   * Splits a phrase query into tokens by whitespace.
   * Whitespace is first normalized to single spaces, then the string is
   * trimmed and split on runs of whitespace.
   *
   * @param {string} query - The query string to tokenize
   * @returns {string[]} Array of tokens. Empty array if query is empty/whitespace only.
   */
  function splitPhraseTokens(query) {
    if (query === null || query === undefined) {
      return [];
    }
    const normalized = normalizeWhitespace(query).trim();
    if (normalized === '') {
      return [];
    }
    return normalized.split(/\s+/);
  }

  /**
   * Returns a phrase (multi-word) matcher for the specified search mode.
   *
   * The returned function accepts `(docWords, query)` where `docWords` is the
   * array of words in the inscription (e.g. `entry.normalisation_norse_words`)
   * and `query` is the phrase to search for. It returns an array of matched
   * windows; each window is an array of word indices `[i, i+1, …, i+N-1]`.
   *
   * Per-operator semantics (N = number of tokens in the phrase, N ≥ 2):
   *   - exact: every token must exactly equal the corresponding consecutive
   *     doc word.
   *   - includes / contains: every token must appear as a substring of the
   *     corresponding consecutive doc word. This mirrors single-word
   *     `contains` (which is `String.includes`) and is consistent across
   *     every position, so e.g. "es satt" matches "es sattr" and "e sat"
   *     matches "es sattr".
   *   - beginsWith: tokens 0..N-2 must equal doc words exactly; the last
   *     doc word must start with the last token.
   *   - endsWith: tokens 1..N-1 must equal doc words exactly; the first
   *     doc word must end with the first token.
   *
   * Windows may appear anywhere in the doc (not anchored to start/end).
   *
   * @param {string} searchMode - One of 'exact', 'beginsWith', 'endsWith',
   *                              'includes', 'contains'.
   * @param {Object} options - Additional options
   * @param {boolean} [options.ignoreCase=false]
   * @param {boolean} [options.includeSpecialSymbols=false]
   * @returns {Function} (docWords, query) => number[][]
   */
  function getPhraseMatchFunction(searchMode, options = {}) {
    const { ignoreCase = false, includeSpecialSymbols = false } = options;
    const normalizedSearchMode = searchMode === 'contains' ? 'includes' : searchMode;

    const prepareString = (str) => {
      let preparedValue = prepareForComparison(str, ignoreCase);
      if (!includeSpecialSymbols) {
        preparedValue = stripSpecialSymbols(preparedValue);
      }
      return preparedValue;
    };

    // Reduce a doc word to its comparable alternatives (handles personal-name
    // annotations like "/X" splitting into multiple candidates).
    const prepareDocWordVariants = (word) => {
      if (word.includes('&#x2F;') || word.includes('/')) {
        return word.split(/&#x2F;|\//).map(name => {
          return prepareString(name.trim().replace(/^(&quot;|")/, ''));
        });
      }
      return [prepareString(word)];
    };

    const docWordEquals = (docWord, tokenPrepared) => {
      return prepareDocWordVariants(docWord).some(v => v === tokenPrepared);
    };

    const docWordStartsWith = (docWord, tokenPrepared) => {
      return prepareDocWordVariants(docWord).some(v => v.startsWith(tokenPrepared));
    };

    const docWordEndsWith = (docWord, tokenPrepared) => {
      return prepareDocWordVariants(docWord).some(v => v.endsWith(tokenPrepared));
    };

    const docWordIncludes = (docWord, tokenPrepared) => {
      return prepareDocWordVariants(docWord).some(v => v.includes(tokenPrepared));
    };

    // Decide the comparison to apply at position `j` of an N-token window.
    const compareAt = (docWord, token, j, n) => {
      const isFirst = j === 0;
      const isLast = j === n - 1;
      switch (normalizedSearchMode) {
        case 'includes':
          // Every token is a substring of the corresponding doc word.
          return docWordIncludes(docWord, token);
        case 'beginsWith':
          return isLast ? docWordStartsWith(docWord, token) : docWordEquals(docWord, token);
        case 'endsWith':
          return isFirst ? docWordEndsWith(docWord, token) : docWordEquals(docWord, token);
        case 'exact':
        default:
          return docWordEquals(docWord, token);
      }
    };

    return (docWords, query) => {
      const tokens = splitPhraseTokens(query).map(prepareString);
      const windows = [];
      const n = tokens.length;
      if (
        n === 0 ||
        tokens.some(token => token.length === 0) ||
        !Array.isArray(docWords) ||
        docWords.length < n
      ) {
        return windows;
      }

      for (let i = 0; i <= docWords.length - n; i++) {
        let matches = true;
        for (let j = 0; j < n; j++) {
          if (!compareAt(docWords[i + j], tokens[j], j, n)) {
            matches = false;
            break;
          }
        }
        if (matches) {
          const window = [];
          for (let j = 0; j < n; j++) window.push(i + j);
          windows.push(window);
        }
      }

      return windows;
    };
  }

  /**
   * Returns field mapping for supported directional word searches.
   * @param {string} searchDirection - Direction identifier
   * @returns {{normalisationField: string, fromField: string, toField: string}|null}
   */
  function getSearchDirectionConfig(searchDirection) {
    switch (searchDirection) {
      case 'norseToTransliteration':
        return {
          normalisationField: 'normalisation_norse',
          fromField: 'normalisation_norse',
          toField: 'transliteration',
        };
      case 'scandinavianToTransliteration':
        return {
          normalisationField: 'normalisation_scandinavian',
          fromField: 'normalisation_scandinavian',
          toField: 'transliteration',
        };
      case 'transliterationToNorse':
        return {
          normalisationField: 'normalisation_norse',
          fromField: 'transliteration',
          toField: 'normalisation_norse',
        };
      case 'transliterationToScandinavian':
        return {
          normalisationField: 'normalisation_scandinavian',
          fromField: 'transliteration',
          toField: 'normalisation_scandinavian',
        };
      default:
        return null;
    }
  }

  var searchCore = /*#__PURE__*/Object.freeze({
    __proto__: null,
    getPhraseMatchFunction: getPhraseMatchFunction,
    getSearchDirectionConfig: getSearchDirectionConfig,
    getWordSearchFunction: getWordSearchFunction,
    isPersonalName: isPersonalName,
    normalizeWhitespace: normalizeWhitespace,
    prepareForComparison: prepareForComparison,
    splitPhraseTokens: splitPhraseTokens,
    stripSpecialSymbols: stripSpecialSymbols
  });

  /**
   * EDA-page helpers. Source file bundled by rollup into
   * `rundatanet/static/runes/eda.min.js` and exposed on `window` by
   * `eda.js` (the bundle entry).
   */

  // Debounce function
  function debounce(func, wait) {
    let timeout;
    return function(...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
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
    const punctuationSource = "(·|:|×|¤|'|\\||\\+|÷|¶|\\(|\\)|\\[|\\])+";
    //const punctuationSource = "([·|:×¤'+÷¶()|[\]\\])+";
    const reg = new RegExp(sourceIsEscaped ? escapeHtml(wordBoundariesSource) : wordBoundariesSource, 'g');
    // regex used to check if detected word is pure punctuational
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

  // Utility function to get display name for a field
  function getFieldDisplayName(fieldName) {
    switch (fieldName) {
      case 'signature_text':
        return 'Signature';
      case 'normalisation_norse':
        return 'Normalisation Norse';
      case 'normalisation_scandinavian':
        return 'Normalisation Scandinavian';
      case 'transliteration':
        return 'Transliteration';
      default:
        return fieldName;
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

  var edaScripts = /*#__PURE__*/Object.freeze({
    __proto__: null,
    debounce: debounce,
    escapeHtml: escapeHtml,
    getFieldDisplayName: getFieldDisplayName,
    getWordBoundaries: getWordBoundaries
  });

  /** Pure helpers for LoRI's reviewed lemma search. */

  const PILOT_LEMMAS = Object.freeze([
    { id: 'KIN001', norse: 'faðir', scandinavian: 'faður' },
    { id: 'KIN002', norse: 'móðir', scandinavian: 'moður' },
    { id: 'KIN005', norse: 'bróðir', scandinavian: 'broðir' },
  ]);

  const LEMMA_ALIASES = new Map(
    PILOT_LEMMAS.flatMap(lemma => [
      [lemma.id.toLocaleLowerCase(), lemma.id],
      [lemma.norse.toLocaleLowerCase(), lemma.id],
      [lemma.scandinavian.toLocaleLowerCase(), lemma.id],
    ])
  );

  function resolveLemmaQuery(query) {
    return LEMMA_ALIASES.get(String(query ?? '').trim().toLocaleLowerCase()) ?? null;
  }

  function groupLemmaRowsBySignature(rows, lemmaId) {
    const grouped = new Map();
    rows.forEach(row => {
      if (row.lemma_id !== lemmaId) {
        return;
      }
      const signatureId = String(row.signature_id);
      if (!grouped.has(signatureId)) {
        grouped.set(signatureId, []);
      }
      grouped.get(signatureId).push(row);
    });
    return grouped;
  }

  function getLemmaSearchResults(dbRows, lemmaRows, lemmaId) {
    const matchesBySignature = groupLemmaRowsBySignature(lemmaRows, lemmaId);

    return dbRows.map(entry => {
      const lemmaMatches = matchesBySignature.get(String(entry.signature_id)) ?? [];
      if (lemmaMatches.length === 0) {
        return null;
      }

      const matchedWords = Array.from(
        new Set(lemmaMatches.map(row => Number(row.word_index)))
      ).sort((left, right) => left - right);

      return {
        ...entry,
        matchedWords,
        lemmaMatches,
        numFoundNames: 0,
      };
    }).filter(Boolean);
  }

  function attestationKey(row, rowIndex) {
    if (
      row.counting_rule === 'count_once_per_attestation_group'
      && row.attestation_group_id
    ) {
      return `group:${row.attestation_group_id}`;
    }
    return `candidate:${row.candidate_id || rowIndex}`;
  }

  function countLemmaAttestations(rows) {
    return new Set(rows.map(attestationKey)).size;
  }

  function cleanIndexedToken(value) {
    return String(value ?? '')
      .replace(/&quot;|"/g, '')
      .trim()
      .replace(/^[,:!?;.]+|[,:!?;.]+$/g, '')
      .trim();
  }

  function cleanLemmaRelationTransliteration(value) {
    return cleanIndexedToken(value).replace(/[()[\]¶]/g, '').trim();
  }

  function incrementVariantCounts(counts, values) {
    const rowValues = new Set(values.map(cleanIndexedToken).filter(Boolean));
    rowValues.forEach(value => counts.set(value, (counts.get(value) ?? 0) + 1));
  }

  function mostFrequentValue(counts) {
    return Array.from(counts)
      .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))[0]?.[0] ?? '';
  }

  function buildLemmaRelationRows(rows) {
    const relationGroups = new Map();

    rows.forEach((row, rowIndex) => {
      const key = [
        row.lemma_id,
        row.accepted_case,
        row.accepted_number,
        row.accepted_gender,
      ].join('\u0000');

      if (!relationGroups.has(key)) {
        relationGroups.set(key, {
          lemmaId: row.lemma_id,
          lemma: row.lemma_norse,
          grammaticalCase: row.accepted_case,
          number: row.accepted_number,
          gender: row.accepted_gender,
          norseAcceptedForms: new Map(),
          norseTokens: new Map(),
          normalizedTokens: new Map(),
          transliterations: new Map(),
          attestationKeys: new Set(),
          signatures: new Map(),
          readingVariants: new Set(),
          certaintyCounts: new Map(),
          groupedReadingAttestations: new Set(),
          matches: [],
        });
      }

      const group = relationGroups.get(key);
      incrementVariantCounts(group.normalizedTokens, [
        row.normalisation_norse,
        row.normalisation_scandinavian,
      ]);
      incrementVariantCounts(group.norseTokens, [row.normalisation_norse]);
      if (row.accepted_form_layer === 'norse') {
        incrementVariantCounts(group.norseAcceptedForms, [row.accepted_form]);
      }
      incrementVariantCounts(group.transliterations, [
        cleanLemmaRelationTransliteration(row.transliteration),
      ]);
      const readingVariant = cleanIndexedToken(row.reading_variant);
      if (readingVariant) {
        group.readingVariants.add(readingVariant);
      }
      const certainty = String(row.lemma_certainty || 'not specified');
      group.certaintyCounts.set(certainty, (group.certaintyCounts.get(certainty) ?? 0) + 1);
      if (
        row.counting_rule === 'count_once_per_attestation_group'
        && row.attestation_group_id
      ) {
        group.groupedReadingAttestations.add(row.attestation_group_id);
      }
      group.attestationKeys.add(attestationKey(row, rowIndex));
      group.signatures.set(String(row.signature_id), row.signature);
      group.matches.push(row);
    });

    const caseOrder = new Map([
      ['nominative', 0],
      ['genitive', 1],
      ['dative', 2],
      ['accusative', 3],
      ['oblique', 4],
      ['nominative_or_accusative', 5],
    ]);
    const numberOrder = new Map([
      ['singular', 0],
      ['plural', 1],
    ]);

    return Array.from(relationGroups.values(), group => {
      const normalizedTokens = Array.from(
        group.normalizedTokens,
        ([value, count]) => ({ value, count })
      ).sort((left, right) => left.value.localeCompare(right.value));
      const transliterations = Array.from(
        group.transliterations,
        ([value, count]) => ({ value, count })
      ).sort((left, right) => left.value.localeCompare(right.value));

      return {
        lemmaId: group.lemmaId,
        lemma: group.lemma,
        form: mostFrequentValue(group.norseAcceptedForms)
          || mostFrequentValue(group.norseTokens)
          || group.lemma,
        grammaticalCase: group.grammaticalCase,
        number: group.number,
        gender: group.gender,
        normalizedTokens,
        transliterations,
        attestations: group.attestationKeys.size,
        rows: group.matches.length,
        signatures: Array.from(group.signatures, ([id, signature]) => ({ id, signature })),
        readingVariants: Array.from(group.readingVariants).sort(),
        certaintyCounts: Array.from(
          group.certaintyCounts,
          ([certainty, count]) => ({ certainty, count })
        ).sort((left, right) => left.certainty.localeCompare(right.certainty)),
        includesProbable: group.certaintyCounts.has('probable'),
        hasGroupedReadingVariants: group.groupedReadingAttestations.size > 0,
        matches: group.matches,
      };
    }).sort((left, right) => {
      const lemmaComparison = left.lemma.localeCompare(right.lemma);
      if (lemmaComparison !== 0) {
        return lemmaComparison;
      }
      const leftCase = caseOrder.get(left.grammaticalCase) ?? 99;
      const rightCase = caseOrder.get(right.grammaticalCase) ?? 99;
      const leftNumber = numberOrder.get(left.number) ?? 99;
      const rightNumber = numberOrder.get(right.number) ?? 99;
      return leftCase - rightCase
        || leftNumber - rightNumber
        || left.form.localeCompare(right.form);
    });
  }

  var edaLemma = /*#__PURE__*/Object.freeze({
    __proto__: null,
    PILOT_LEMMAS: PILOT_LEMMAS,
    buildLemmaRelationRows: buildLemmaRelationRows,
    countLemmaAttestations: countLemmaAttestations,
    getLemmaSearchResults: getLemmaSearchResults,
    groupLemmaRowsBySignature: groupLemmaRowsBySignature,
    resolveLemmaQuery: resolveLemmaQuery
  });

  /**
   * Highlight whole words in a string given their pre-computed character
   * boundaries. Used for word-aligned fields (transliteration and the two
   * normalisations). The boundaries are sorted in-place before rendering.
   *
   * @param {string} str - The (already HTML-escaped) string to render.
   * @param {Array<{start: number, end: number, text: string}>} wordBoundaries
   * @returns {string} The string with matched words wrapped in highlight spans.
   */
  function highlightWordsFromWordBoundaries(str, wordBoundaries) {
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

  // EDA-page bundle entry. Rollup bundles all imports into
  // `rundatanet/static/runes/eda.min.js`. Everything here is exposed on
  // `window` because the EDA page uses inline `<script>` blocks.

  Object.assign(window, searchCore, edaScripts, edaLemma, { highlightWordsFromWordBoundaries });

})();
