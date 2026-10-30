// EDA-page bundle entry. Rollup bundles all imports into
// `rundatanet/static/runes/eda.min.js`. Everything here is exposed on
// `window` because the EDA page uses inline `<script>` blocks.
import * as edaScripts from './eda_scripts.js';
import * as edaLemma from './eda_lemma.js';
import * as searchCore from './search_core.js';
import { highlightWordsFromWordBoundaries } from './index_scripts.js';

Object.assign(window, searchCore, edaScripts, edaLemma, { highlightWordsFromWordBoundaries });
