import { readFileSync } from 'node:fs';
import { test } from 'uvu';
import * as assert from 'uvu/assert';
import { buildLemmaParadigmRows, getLemmaSearchResults } from '../../runes/js/eda_lemma.js';

const index = JSON.parse(readFileSync('rundatanet/static/runes/lemma_index.json', 'utf8'));
const lemmaIds = ['KIN001', 'KIN002', 'KIN005'];

test('each pilot lemma exposes all eight cells even with zero search results', () => {
  for (const lemmaId of lemmaIds) {
    const rows = buildLemmaParadigmRows([], lemmaId);
    assert.is(rows.length, 8);
    assert.is(new Set(rows.map(r => `${r.grammaticalCase}:${r.number}`)).size, 8);
    assert.ok(rows.every(r => r.rows === 0 && r.attestations === 0 && r.expectedOnly));
    assert.ok(rows.every(r => r.form && r.matches.length === 0 && r.transliterations.length === 0));
  }
});

test('brother dat. sg. is zero while the missing Ög 136 dat. pl. is one', () => {
  const rows = buildLemmaParadigmRows(index, 'KIN005');
  const singular = rows.find(r => r.grammaticalCase === 'dative' && r.number === 'singular');
  const plural = rows.find(r => r.grammaticalCase === 'dative' && r.number === 'plural');
  assert.is(singular.form, 'bróður');
  assert.is(singular.attestations, 0);
  assert.is(plural.attestations, 1);
  assert.is(plural.matches[0].signature, 'Ög 136');
  assert.is(plural.matches[0].word_index, 105);
});

test('father and mother retain their reviewed dat. sg. examples and certainty', () => {
  const father = buildLemmaParadigmRows(index, 'KIN001').find(r => r.grammaticalCase === 'dative' && r.number === 'singular');
  const mother = buildLemmaParadigmRows(index, 'KIN002').find(r => r.grammaticalCase === 'dative' && r.number === 'singular');
  assert.is(father.attestations, 1);
  assert.is(father.matches[0].signature, 'Vg 80');
  assert.is(father.matches[0].lemma_certainty, 'uncertain (Peterson)');
  assert.is(mother.attestations, 1);
  assert.is(mother.matches[0].signature, 'N 7');
});

test('father plural supplement is exported once per token', () => {
  const plural = buildLemmaParadigmRows(index, 'KIN001').find(r => r.grammaticalCase === 'accusative' && r.number === 'plural');
  assert.is(plural.attestations, 2);
  assert.equal(plural.signatures.map(r => r.signature).sort(), ['U 1032', 'U 749']);
});

test('syncretic case stays separate and all counts reconcile without duplication', () => {
  for (const lemmaId of lemmaIds) {
    const rows = buildLemmaParadigmRows(index, lemmaId);
    const matched = index.filter(r => r.lemma_id === lemmaId);
    assert.is(rows.reduce((n,r)=>n+r.rows,0), matched.length);
    assert.is(new Set(rows.flatMap(r=>r.matches).map(r=>r.candidate_id)).size, matched.length);
    assert.is(rows.filter(r=>!r.unresolvedAnalysis).length, 8);
  }
  const brother = buildLemmaParadigmRows(index, 'KIN005');
  assert.is(brother.filter(r=>r.unresolvedAnalysis).length, 1);
  assert.is(brother.find(r=>r.unresolvedAnalysis).grammaticalCase, 'nominative_or_accusative');
});

test('zero and counts follow the selected period, not the whole lemma index', () => {
  const entry = {signature_id:327, dating:'Viking age 9th century'};
  const viking = getLemmaSearchResults([entry],index,'KIN005','vikingAge');
  const medieval = getLemmaSearchResults([entry],index,'KIN005','medieval');
  assert.is(buildLemmaParadigmRows(viking.flatMap(e=>e.lemmaMatches),'KIN005')
    .find(r=>r.grammaticalCase==='dative' && r.number==='plural').attestations,1);
  assert.ok(buildLemmaParadigmRows(medieval.flatMap(e=>e.lemmaMatches),'KIN005').every(r=>r.attestations===0));
});

test('empty paradigm rows have a definition of zero and no empty examples control', () => {
  const template = readFileSync('rundatanet/templates/runes/eda.html','utf8');
  assert.ok(template.includes('0 = no reviewed attestations in the current selection.'));
  assert.ok(template.includes('if (row.rows === 0)'));
  assert.not.ok(template.includes('Paradigm form'));
});

test.run();
