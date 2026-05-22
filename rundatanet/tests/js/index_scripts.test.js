import { test } from 'uvu';
import * as assert from 'uvu/assert';
//import Database from 'better-sqlite3';
import { convertDbToKeyMap, fetchAllImages, makeImagesMarkup, highlightSubstringRanges } from '../../runes/js/index_scripts.js';
import { mockDb } from './mockDb.js';

test('convertDbToKeyMap() function', async () => {
  //const dbPath = 'rundatanet/static/runes/runes.sqlite3';
  //const db = new Database(dbPath, { readonly: true });
  const result = convertDbToKeyMap(mockDb);

  const expectedInscriptions = 6815;
  assert.is(result.size, expectedInscriptions, `The resulting object should be of size: ${expectedInscriptions}`);

  //const expectedNum = 3;
  //assert.is(Object.keys(result).length, expectedNum, `The resulting object should contain ${expectedNum} keys/values`);
});

test('fetchAllImages() function', async () => {
  const result = fetchAllImages(mockDb);
  const expectedDirectUrl = "https://pub.raa.se/dokumentation/00c46e71-67aa-4893-b5a2-de89615a4de9/visning/1/miniatyr";
  const expectedLinkUrl = "https://pub.raa.se/visa/dokumentation/00c46e71-67aa-4893-b5a2-de89615a4de9";

  // images of the first inscription
  const images = result['1'];

  assert.is(images.links.length, 41, `The first inscription should have 41 images`);

  assert.is(images.links[0].direct, expectedDirectUrl, `The first inscription should have a direct link to: ${expectedDirectUrl}`);
  assert.is(images.links[0].indirect, expectedLinkUrl, `The first inscription should have a link to: ${expectedLinkUrl}`);
});

test('makeImagesMarkup() function', async () => {
  const images = {
    links: [
      {
        direct: "http://example.com/image1.jpg",
        indirect: "http://example.com/image1-link"
      }
    ],
  };
  const expectedDirect = `<div class="rundata-image-gallery"><figure class="rundata-image-item"><a href="${images.links[0].indirect}" contentEditable="false" target="_blank" class="rundata-image-link"><img src="${images.links[0].direct}" class="rundata-image-avatar" alt="Inscription image"></a><figcaption class="rundata-image-source">source: <a href="${images.links[0].indirect}" contentEditable="false" target="_blank">example.com</a></figcaption></figure></div>`;
  const results = makeImagesMarkup(images);
  assert.is(results.directImages, expectedDirect, `The direct images markup should be: ${expectedDirect}`);
  assert.is(results.indirectImages, '', `The indirect images markup should be empty when no indirect-only images exist`);
});

// ---------------------------------------------------------------------------
// Tests for highlightSubstringRanges
// ---------------------------------------------------------------------------

test('highlightSubstringRanges wraps a single range and escapes surrounding text', () => {
  const str = 'raised this stone';
  const result = highlightSubstringRanges(str, [[12, 17]]);
  assert.is(result, 'raised this <span class="highlight">stone</span>');
});

test('highlightSubstringRanges supports multiple non-overlapping ranges', () => {
  const str = 'the stone and the stone';
  const ranges = [[4, 9], [18, 23]];
  const result = highlightSubstringRanges(str, ranges);
  assert.is(
    result,
    'the <span class="highlight">stone</span> and the <span class="highlight">stone</span>'
  );
});

test('highlightSubstringRanges merges overlapping ranges', () => {
  const str = 'abcdefghij';
  // [2,6)=cdef, [4,8)=efgh — overlapping → merged [2,8)=cdefgh
  const ranges = [[2, 6], [4, 8]];
  const result = highlightSubstringRanges(str, ranges);
  assert.is(result, 'ab<span class="highlight">cdefgh</span>ij');
});

test('highlightSubstringRanges merges adjacent ranges', () => {
  const str = 'abcdef';
  const ranges = [[0, 2], [2, 4]]; // adjacent → merged [0,4)
  const result = highlightSubstringRanges(str, ranges);
  assert.is(result, '<span class="highlight">abcd</span>ef');
});

test('highlightSubstringRanges sorts unsorted ranges', () => {
  const str = 'one two three';
  // Supplied in reverse order; should still render correctly.
  const ranges = [[8, 13], [0, 3]];
  const result = highlightSubstringRanges(str, ranges);
  assert.is(
    result,
    '<span class="highlight">one</span> two <span class="highlight">three</span>'
  );
});

test('highlightSubstringRanges escapes HTML inside and outside the matched range', () => {
  const str = '<b>stone</b> & <i>hammer</i>';
  // Highlight the substring "stone" (chars 3..8).
  const result = highlightSubstringRanges(str, [[3, 8]]);
  assert.is(
    result,
    '&lt;b&gt;<span class="highlight">stone</span>&lt;&#x2F;b&gt; &amp; &lt;i&gt;hammer&lt;&#x2F;i&gt;'
  );
});

test('highlightSubstringRanges with no ranges returns the escaped string', () => {
  const str = '<stone>';
  assert.is(highlightSubstringRanges(str, []), '&lt;stone&gt;');
});

test('highlightSubstringRanges clamps out-of-bound ranges', () => {
  const str = 'abcdef';
  // [-2,2) → clamped to [0,2); [4,999) → clamped to [4,6)
  const ranges = [[-2, 2], [4, 999]];
  const result = highlightSubstringRanges(str, ranges);
  assert.is(
    result,
    '<span class="highlight">ab</span>cd<span class="highlight">ef</span>'
  );
});

test('highlightSubstringRanges drops invalid (zero/negative-length) ranges', () => {
  const str = 'abcdef';
  const ranges = [[3, 3], [5, 2], [1, 2]];
  const result = highlightSubstringRanges(str, ranges);
  assert.is(result, 'a<span class="highlight">b</span>cdef');
});

test('highlightSubstringRanges handles null and undefined input', () => {
  assert.is(highlightSubstringRanges(null, [[0, 1]]), '');
  assert.is(highlightSubstringRanges(undefined, [[0, 1]]), '');
});

test('highlightSubstringRanges handles empty string input', () => {
  assert.is(highlightSubstringRanges('', [[0, 5]]), '');
});

test.run();
