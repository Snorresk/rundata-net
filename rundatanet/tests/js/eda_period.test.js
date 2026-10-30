import { test } from 'uvu';
import * as assert from 'uvu/assert';
import { readFileSync } from 'node:fs';
import { escapeHtml, getWordBoundaries } from '../../runes/js/eda_scripts.js';
import { getWordTimePeriods, isEntryInTimePeriod, isWordInTimePeriod } from '../../runes/js/eda_period.js';
import { getLemmaSearchResults, countLemmaAttestations, buildLemmaRelationRows } from '../../runes/js/eda_lemma.js';

const lemmaIndex = JSON.parse(readFileSync('rundatanet/static/runes/lemma_index.json', 'utf8'));
const so32 = {
  signature_id: 715, signature_text: 'Sö 32',
  dating: 'Proto-Norse period and Viking age, §A=Proto-Norse 375/400-560/570 (Imer 2007), §B=Viking Age',
  normalisation_norse: '§A "Harja, "Leugaz §B "Skammhals ok "Ólôf þau létu gera merki þessi eptir "Svein, fôður sinn. "Guð hjalpi sálu hans.',
  normalisation_scandinavian: '§A "Harja, "Leugaz §B "Skammhals ok "Olof þau letu gæra mærki þausi æftiR "Svæin, faður sinn. "Guð hialpi salu hans.',
  transliteration: '§A harija ÷ leugaz §B skanmals auk × olauf × þau × litu × kiara × merki × þausi × eftiR × suain × faþur × sin × kuþ × hialbi salu hans',
};

test('Sö 32 faðir is absent from Proto-Norse, present in Viking Age and All', () => {
  assert.is(getLemmaSearchResults([so32], lemmaIndex, 'KIN001', 'protoNorse').length, 0);
  for (const period of ['all', 'vikingAge']) {
    const results = getLemmaSearchResults([so32], lemmaIndex, 'KIN001', period);
    assert.equal(results[0].matchedWords, [14]);
    const rows = results[0].lemmaMatches;
    assert.is(countLemmaAttestations(rows), 1);
    assert.is(buildLemmaRelationRows(rows)[0].attestations, 1);
    assert.equal(rows[0].attestation_periods, ['vikingAge']);
    assert.is(rows[0].inscription_section, 'B');
    assert.is(rows[0].dating_basis, 'section');
  }
});

test('ordinary word searches use each word section in all three layers', () => {
  for (const layer of ['normalisation_norse', 'normalisation_scandinavian', 'transliteration']) {
    assert.ok(isWordInTimePeriod(so32, 1, 'protoNorse', layer));
    assert.not.ok(isWordInTimePeriod(so32, 1, 'vikingAge', layer));
    assert.not.ok(isWordInTimePeriod(so32, 14, 'protoNorse', layer));
    assert.ok(isWordInTimePeriod(so32, 14, 'vikingAge', layer));
  }
});

test('a lemma shared by both sections retains only the selected token', () => {
  const rows = [1, 14].map(i => ({ candidate_id: `test-${i}`, signature_id: 715,
    lemma_id: 'TEST', word_index: i }));
  assert.equal(getLemmaSearchResults([so32], rows, 'TEST', 'protoNorse')[0].matchedWords, [1]);
  assert.equal(getLemmaSearchResults([so32], rows, 'TEST', 'vikingAge')[0].matchedWords, [14]);
  assert.equal(getLemmaSearchResults([so32], rows, 'TEST')[0].matchedWords, [1, 14]);
});

test('section dates follow labels even when their order or signum differs', () => {
  const entry = { signature_text: 'Another object', dating: 'Middle ages and Viking age, §B: Middle ages, §A: Viking age',
    normalisation_norse: '§B kona §A faðir' };
  assert.ok(isWordInTimePeriod(entry, 1, 'medieval'));
  assert.not.ok(isWordInTimePeriod(entry, 1, 'vikingAge'));
  assert.ok(isWordInTimePeriod(entry, 3, 'vikingAge'));
});

test('unresolved sections of a mixed-period object never inherit all periods', () => {
  const entry = { ...so32, normalisation_norse: '§C faðir' };
  assert.equal(getWordTimePeriods(entry, 1).periods, []);
  assert.not.ok(isWordInTimePeriod(entry, 1, 'protoNorse'));
  assert.not.ok(isWordInTimePeriod(entry, 1, 'vikingAge'));
  assert.ok(isWordInTimePeriod(entry, 1, 'all'));
  assert.not.ok(isWordInTimePeriod(entry, 999, 'protoNorse'));
});

test('corrected HTML boundaries determine the section without token renumbering', () => {
  const entry = { ...so32 };
  entry.normalisation_norse_html = escapeHtml(entry.normalisation_norse);
  entry.normalisation_norse_word_boundaries = getWordBoundaries(entry.normalisation_norse_html, true)
    .filter((_, i) => i !== 1);
  assert.equal(getWordTimePeriods(entry, 13).periods, ['vikingAge']);
});

test('single-period records, numeric section dates and section ranges retain their period', () => {
  const entry = { dating: 'Middle ages §A-§E: 1280–1296, §F: 14th century',
    normalisation_norse: '§A Pétr §F Jón' };
  assert.ok(isWordInTimePeriod(entry, 1, 'medieval'));
  assert.ok(isWordInTimePeriod(entry, 3, 'medieval'));
  const range = { dating: 'Proto-Norse and Viking age, §A-§C: Proto-Norse, §D: Viking age',
    normalisation_norse: '§B Harja §D faðir' };
  assert.ok(isWordInTimePeriod(range, 1, 'protoNorse'));
  assert.not.ok(isWordInTimePeriod(range, 3, 'protoNorse'));
  for (const [dating, period] of [['P', 'protoNorse'], ['V', 'vikingAge'], ['M', 'medieval']]) {
    assert.ok(isWordInTimePeriod({ dating }, 0, period));
  }
});

test('pre-Viking is not Viking Age; a genuine uncertain interval remains searchable', () => {
  assert.not.ok(isEntryInTimePeriod({ dating: 'Proto-Norse period, pre-Viking Age' }, 'vikingAge'));
  for (const period of ['protoNorse', 'vikingAge']) {
    assert.ok(isWordInTimePeriod({ dating: 'Proto-Norse period/Viking age 600–800' }, 0, period));
  }
});

test('a dated exception overrides the default period only for its own section', () => {
  const entry = { dating: 'Viking age, except D, which is probably Middle ages, 12th century',
    normalisation_norse: '§A kona §D faðir' };
  assert.ok(isWordInTimePeriod(entry, 1, 'vikingAge'));
  assert.not.ok(isWordInTimePeriod(entry, 1, 'medieval'));
  assert.ok(isWordInTimePeriod(entry, 3, 'medieval'));
  assert.not.ok(isWordInTimePeriod(entry, 3, 'vikingAge'));
});

test('EDA connects the selected period to lemma and ordinary word matching', () => {
  const template = readFileSync('rundatanet/templates/runes/eda.html', 'utf8');
  assert.ok(template.includes('getLemmaSearchResults(dbAsJson, lemmaIndex, lemmaId, getSelectedTimePeriod())'));
  assert.is((template.match(/isWordInTimePeriod\(entry, i, selectedPeriod/g) ?? []).length, 3);
});

test.run();
