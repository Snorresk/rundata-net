/**
 * Shared search helpers used by both the main index page and the EDA page.
 */

/**
 * Checks if a given word is a personal name.
 * @param {string} word - The word to check.
 * @returns {boolean} - True if the word is a personal name, false otherwise.
 */
export function isPersonalName(word) {
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
export function normalizeWhitespace(value) {
  return String(value).replace(/\s/g, ' ');
}

/**
 * Prepares a string for comparison by normalizing whitespace and optionally lowercasing.
 * @param {*} value - The value to prepare
 * @param {boolean} ignoreCase - Whether to lowercase the string
 * @returns {string} The prepared string
 */
export function prepareForComparison(value, ignoreCase) {
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
export function stripSpecialSymbols(str) {
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
export function getWordSearchFunction(searchMode, options = {}) {
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
export function splitPhraseTokens(query) {
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
export function getPhraseMatchFunction(searchMode, options = {}) {
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
export function getSearchDirectionConfig(searchDirection) {
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
