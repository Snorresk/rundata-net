import { readFileSync } from 'node:fs';
import { test } from 'uvu';
import * as assert from 'uvu/assert';

import {
  buildLemmaRelationRows,
  getLemmaSearchResults,
  resolveLemmaQuery,
} from '../../runes/js/eda_lemma.js';
import { getWordSearchFunction } from '../../runes/js/search_core.js';

const lemmaIndex = JSON.parse(
  readFileSync('rundatanet/static/runes/lemma_index.json', 'utf8')
);

test('lemma query resolves reviewed Norse, Scandinavian, and ID aliases', () => {
  assert.is(resolveLemmaQuery('móðir'), 'KIN002');
  assert.is(resolveLemmaQuery('moður'), 'KIN002');
  assert.is(resolveLemmaQuery('KIN002'), 'KIN002');
  assert.is(resolveLemmaQuery('bróðir'), 'KIN005');
  assert.is(resolveLemmaQuery('unknown'), null);
});

test('móðir search returns every accepted KIN002 token', () => {
  const motherRows = lemmaIndex.filter(row => row.lemma_id === 'KIN002');
  const dbRows = Array.from(
    new Set(motherRows.map(row => String(row.signature_id))),
    signatureId => ({ signature_id: signatureId })
  );
  const results = getLemmaSearchResults(dbRows, lemmaIndex, 'KIN002');

  assert.is(
    results.flatMap(result => result.lemmaMatches).length,
    motherRows.length
  );
});

test('lemma index excludes ambiguous and unaccepted review rows', () => {
  assert.not.ok(lemmaIndex.some(row => row.review_status === 'ambiguous'));
  assert.not.ok(lemmaIndex.some(row => !row.lemma_id));
  assert.ok(lemmaIndex.every(row => [
    'source_confirmed',
    'source_lemma_new_occurrence',
    'inferred_pattern',
  ].includes(row.review_status)));
});

test('DR 30 P/Q/R variants count as one attestation', () => {
  const dr30Rows = lemmaIndex.filter(row =>
    row.lemma_id === 'KIN002' && row.signature === 'DR 30'
  );
  const relations = buildLemmaRelationRows(dr30Rows);

  assert.is(dr30Rows.length, 3);
  assert.is(relations.length, 1);
  assert.is(relations[0].attestations, 1);
  assert.is(relations[0].rows, 3);
  assert.equal(relations[0].readingVariants, ['P', 'Q', 'R']);
  assert.equal(relations[0].transliterations, [{ value: 'mþu', count: 3 }]);
  assert.ok(relations[0].hasGroupedReadingVariants);
});

test('móðir relations contain several grammatical case groups', () => {
  const relations = buildLemmaRelationRows(
    lemmaIndex.filter(row => row.lemma_id === 'KIN002')
  );
  const cases = new Set(relations.map(row => row.grammaticalCase));
  const nominativeSingular = relations.filter(row =>
    row.grammaticalCase === 'nominative' && row.number === 'singular'
  );

  assert.ok(cases.has('nominative'));
  assert.ok(cases.has('accusative'));
  assert.ok(cases.has('genitive'));
  assert.ok(cases.has('dative'));
  assert.is(nominativeSingular.length, 1);
  assert.is(nominativeSingular[0].form, 'móðir');
  assert.is(nominativeSingular[0].rows, 76);
  assert.is(relations.reduce((sum, row) => sum + row.rows, 0), 158);
  assert.is(relations.reduce((sum, row) => sum + row.attestations, 0), 156);
});

test('lemma relation rows sort singular before plural within a case', () => {
  const fixture = [
    {
      candidate_id: 'plural', lemma_id: 'KIN002', lemma_norse: 'móðir',
      accepted_form_id: 'plural', accepted_form: 'mœðr', accepted_case: 'nominative',
      accepted_number: 'plural', accepted_gender: 'femininum', signature_id: '2',
      signature: 'Test 2', normalisation_norse: 'mœðr', normalisation_scandinavian: 'møðr',
      transliteration: 'mþr', lemma_certainty: 'certain',
    },
    {
      candidate_id: 'singular', lemma_id: 'KIN002', lemma_norse: 'móðir',
      accepted_form_id: 'singular', accepted_form: 'móðir', accepted_case: 'nominative',
      accepted_number: 'singular', accepted_gender: 'femininum', signature_id: '1',
      signature: 'Test 1', normalisation_norse: 'móðir', normalisation_scandinavian: 'moðir',
      transliteration: 'muþiR', lemma_certainty: 'certain',
    },
  ];

  assert.equal(
    buildLemmaRelationRows(fixture).map(row => row.number),
    ['singular', 'plural']
  );
});

test('ordinary contains and exact word searches retain existing behavior', () => {
  const contains = getWordSearchFunction('contains');
  const exact = getWordSearchFunction('exact');

  assert.ok(contains('boand[a]', 'boanda'));
  assert.ok(exact('boand[a]', 'boanda'));
  assert.not.ok(exact('boand[a]', 'boand'));
});

test('EDA offers Lemma and defaults to Old West Norse', () => {
  const template = readFileSync('rundatanet/templates/runes/eda.html', 'utf8');

  assert.ok(template.includes('<option value="lemma">Lemma</option>'));
  assert.match(template, /id="oldWestNorseInput"[^>]*checked/);
  assert.ok(template.includes('scope="rowgroup"'));
  assert.ok(template.includes('Show examples in inscriptions'));
});

test.run();
