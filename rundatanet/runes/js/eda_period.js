/** Periods belong to text sections when an object carries several inscriptions. */
import { getWordBoundaries } from './eda_scripts.js';

const datingCache = new WeakMap();

function periodsInDating(value) {
  const text = String(value ?? '').toLowerCase();
  const periods = [];
  if (/proto[\s\-–—]*norse|urnordisk|^p\b/.test(text)) {
    periods.push('protoNorse');
  }
  // "pre-Viking Age" describes an earlier period, not a Viking-age attestation.
  if (/viking\s+age|^v\b/.test(text.replace(/pre[\s-]*viking\s+age/g, ''))) {
    periods.push('vikingAge');
  }
  if (/middle\s+ages|medieval|^m\b/.test(text)) {
    periods.push('medieval');
  }
  return periods;
}

function datingInfo(entry) {
  if (!datingCache.has(entry)) {
    const dating = String(entry.dating ?? '');
    const markers = Array.from(dating.matchAll(/§([A-Z]+)(?:\s*[-–]\s*§([A-Z]+))?\s*[=:]|except\s+([A-Z]+)\s*,?\s*(?:which\s+is\s+)?/gi));
    const sections = new Map();
    markers.forEach((marker, index) => {
      const end = markers[index + 1]?.index ?? dating.length;
      const periods = periodsInDating(dating.slice(marker.index + marker[0].length, end));
      const first = (marker[1] ?? marker[3]).toUpperCase();
      const last = marker[2]?.toUpperCase();
      if (last && first.length === 1 && last.length === 1) {
        for (let code = first.charCodeAt(0); code <= last.charCodeAt(0); code++) {
          sections.set(String.fromCharCode(code), periods);
        }
      } else {
        sections.set(first, periods);
      }
    });
    datingCache.set(entry, {
      periods: periodsInDating(dating), sections,
      defaultPeriods: periodsInDating(dating.slice(0, markers[0]?.index ?? dating.length)),
    });
  }
  return datingCache.get(entry);
}

export function isEntryInTimePeriod(entry, selectedPeriod = 'all') {
  return selectedPeriod === 'all' || datingInfo(entry).periods.includes(selectedPeriod);
}

export function getWordTimePeriods(entry, wordIndex, layer = 'normalisation_norse') {
  const info = datingInfo(entry);
  if (info.sections.size === 0) {
    return { section: '', periods: info.periods, basis: 'record' };
  }
  const text = String(entry[`${layer}_html`] ?? entry[layer] ?? '');
  // Use the already aligned boundaries, including the EDA's position fixes.
  const boundaries = entry[`${layer}_word_boundaries`] ?? getWordBoundaries(text);
  const boundary = boundaries[Number(wordIndex)];
  if (!boundary) {
    return { section: '', periods: [], basis: 'unresolved' };
  }
  const markers = Array.from(text.slice(0, boundary.end).matchAll(/§([A-Z]+)/g));
  const section = markers.at(-1)?.[1] ?? '';
  // P/Q/R alternatives may occur within a section dated as a whole (e.g. §BP).
  const sectionPeriods = info.sections.get(section) ?? info.sections.get(section.slice(0, 1));
  if (sectionPeriods?.length) {
    return { section, periods: sectionPeriods, basis: 'section' };
  }
  // A single period applies to undated subdivisions too. With mixed periods,
  // an unresolved section must not inherit every period from the object.
  return {
    section,
    periods: info.defaultPeriods.length === 1 ? info.defaultPeriods : [],
    basis: info.defaultPeriods.length === 1 ? 'record' : 'unresolved',
  };
}

export function isWordInTimePeriod(entry, wordIndex, selectedPeriod = 'all', layer = 'normalisation_norse') {
  return selectedPeriod === 'all'
    || getWordTimePeriods(entry, wordIndex, layer).periods.includes(selectedPeriod);
}
