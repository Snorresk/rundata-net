/** Pure helpers for LoRI's reviewed lemma search. */

export const PILOT_LEMMAS = Object.freeze([
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

export function resolveLemmaQuery(query) {
  return LEMMA_ALIASES.get(String(query ?? '').trim().toLocaleLowerCase()) ?? null;
}

export function groupLemmaRowsBySignature(rows, lemmaId) {
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

export function getLemmaSearchResults(dbRows, lemmaRows, lemmaId) {
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

export function countLemmaAttestations(rows) {
  return new Set(rows.map(attestationKey)).size;
}

function cleanIndexedToken(value) {
  return String(value ?? '')
    .replace(/&quot;|"/g, '')
    .trim()
    .replace(/^[,:!?;.]+|[,:!?;.]+$/g, '')
    .trim();
}

function incrementVariantCounts(counts, values) {
  const rowValues = new Set(values.map(cleanIndexedToken).filter(Boolean));
  rowValues.forEach(value => counts.set(value, (counts.get(value) ?? 0) + 1));
}

function mostFrequentValue(counts) {
  return Array.from(counts)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))[0]?.[0] ?? '';
}

export function buildLemmaRelationRows(rows) {
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
    incrementVariantCounts(group.transliterations, [row.transliteration]);
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
