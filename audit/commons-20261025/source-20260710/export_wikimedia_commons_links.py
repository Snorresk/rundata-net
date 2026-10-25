#!/usr/bin/env python3
"""Export likely Wikimedia Commons image links for Rundata inscriptions.

The script is deliberately read-only: it queries Wikimedia Commons, scores
candidate file matches against inscriptions from ``runes.sqlite3``, and writes a
CSV review file. It does not modify ``runes_imagelink``.

Example:
    python utility/export_wikimedia_commons_links.py \
        --db rundatanet/static/runes/runes.sqlite3 \
        --out /tmp/commons_links.csv \
        --signatures "Öl 1" "Sö 140"
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sqlite3
import ssl
import time
import unicodedata
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_FILE_BASE = "https://commons.wikimedia.org/wiki/"
DEFAULT_USER_AGENT = "RundataNetCommonsExport/0.1 (https://rundata.info)"
DEFAULT_MAX_PER_INSCRIPTION = 10
DEFAULT_MIN_CONFIDENCE = 35

HTML_TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Inscription:
    meta_id: int
    signature: str
    canonical_signature: str = ""
    found_location: str = ""
    parish: str = ""
    municipality: str = ""
    current_location: str = ""
    original_site: str = ""


@dataclass
class CommonsCandidate:
    title: str
    page_url: str = ""
    direct_url: str = ""
    thumb_url: str = ""
    mime: str = ""
    width: int | None = None
    height: int | None = None
    categories: list[str] = field(default_factory=list)
    snippet: str = ""
    extmetadata: dict[str, str] = field(default_factory=dict)
    search_queries: set[str] = field(default_factory=set)


@dataclass
class ScoredCandidate:
    candidate: CommonsCandidate
    confidence: int
    reasons: list[str]
    already_in_db: bool


def clean_text(value: Any) -> str:
    """Return plain text from MediaWiki/HTML-ish values."""
    if value is None:
        return ""
    text = str(value)
    text = HTML_TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return SPACE_RE.sub(" ", text).strip()


def fold_text(value: str) -> str:
    """Case/diacritic-insensitive text used for matching."""
    value = clean_text(value).casefold()
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    without_marks = without_marks.replace("æ", "ae").replace("ø", "o").replace("þ", "th").replace("ð", "d")
    without_marks = re.sub(r"[_\-/.,:;()[\]{}]+", " ", without_marks)
    return SPACE_RE.sub(" ", without_marks).strip()


def compact_fold(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", fold_text(value))


def unique_keep_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        value = SPACE_RE.sub(" ", str(value or "")).strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def ascii_variant(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def signature_variants(signature: str) -> list[str]:
    """Generate common Commons spellings for a Rundata signature."""
    signature = SPACE_RE.sub(" ", signature.strip())
    compact = re.sub(r"\s+", "", signature)
    hyphen = re.sub(r"\s+", "-", signature)
    variants = [signature, compact, hyphen]

    ascii_sig = ascii_variant(signature)
    ascii_compact = re.sub(r"\s+", "", ascii_sig)
    ascii_hyphen = re.sub(r"\s+", "-", ascii_sig)
    variants.extend([ascii_sig, ascii_compact, ascii_hyphen])

    # Common English/ASCII renderings in Commons filenames.
    replacements = {
        "Sö": "So",
        "Nä": "Na",
        "Öl": "Ol",
        "Ög": "Og",
        "Þ": "Th",
    }
    for old, new in replacements.items():
        if signature.startswith(old):
            replaced = new + signature[len(old) :]
            variants.extend([replaced, re.sub(r"\s+", "", replaced), re.sub(r"\s+", "-", replaced)])

    return unique_keep_order(variants)


def location_variants(inscription: Inscription) -> list[str]:
    values: list[str] = []
    for raw in (
        inscription.found_location,
        inscription.current_location,
        inscription.parish,
        inscription.municipality,
    ):
        raw = clean_text(raw)
        if not raw:
            continue
        # Remove common Swedish administrative abbreviations and distance notes.
        cleaned = re.sub(r"\b(?:sn|socken|kommun)\b\.?", "", raw, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b\d+(?:[,.]\d+)?\s*m\b.*$", "", cleaned, flags=re.IGNORECASE).strip(" ,.;")
        if cleaned:
            values.append(cleaned)
        if "," in cleaned:
            values.append(cleaned.split(",", 1)[0])
    return unique_keep_order(values)


def build_search_queries(inscription: Inscription, max_queries: int = 8) -> list[str]:
    """Build Commons search strings for one inscription."""
    queries: list[str] = []
    sigs = []
    for signature in unique_keep_order([inscription.signature, inscription.canonical_signature]):
        sigs.extend(signature_variants(signature))
    sigs = unique_keep_order(sigs)
    locs = location_variants(inscription)

    for sig in sigs[:5]:
        queries.append(f'"{sig}" runestone')
        queries.append(f'"{sig}" runic inscription')

    for loc in locs[:4]:
        queries.append(f'"{loc}" runestone')
        queries.append(f'"{loc}" runic inscription')

    if sigs and locs:
        queries.append(f'"{sigs[0]}" "{locs[0]}"')

    return unique_keep_order(queries)[:max_queries]


def extmetadata_value(extmetadata: dict[str, Any], key: str) -> str:
    item = extmetadata.get(key)
    if isinstance(item, dict):
        return clean_text(item.get("value", ""))
    return clean_text(item)


class CommonsClient:
    def __init__(
        self,
        endpoint: str = COMMONS_API,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 30,
        delay: float = 0.25,
        max_retries: int = 4,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.delay = delay
        self.max_retries = max(1, max_retries)
        self.user_agent = user_agent
        self.ssl_context = self._build_ssl_context()

    @staticmethod
    def _build_ssl_context() -> ssl.SSLContext:
        try:
            import certifi  # type: ignore

            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl.create_default_context()

    def _request_json(self, params: dict[str, Any]) -> dict[str, Any]:
        params = {
            "format": "json",
            "formatversion": "2",
            **params,
        }
        url = f"{self.endpoint}?{urllib.parse.urlencode(params, doseq=True)}"
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        last_error: BaseException | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
                    data = response.read()
                break
            except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise
                wait_seconds = min(30.0, self.delay + (2 ** (attempt - 1)))
                print(
                    f"Commons request failed ({type(exc).__name__}); retrying "
                    f"{attempt}/{self.max_retries} after {wait_seconds:.1f}s",
                    flush=True,
                )
                time.sleep(wait_seconds)
        else:
            assert last_error is not None
            raise last_error
        if self.delay:
            time.sleep(self.delay)
        return json.loads(data.decode("utf-8"))

    def search_file_titles(self, query: str, limit: int) -> list[tuple[str, str]]:
        payload = self._request_json(
            {
                "action": "query",
                "list": "search",
                "srnamespace": 6,
                "srsearch": query,
                "srlimit": limit,
                "srprop": "snippet",
            }
        )
        results = payload.get("query", {}).get("search", [])
        return [(str(item.get("title", "")), clean_text(item.get("snippet", ""))) for item in results]

    def fetch_file_details(self, titles: Sequence[str]) -> dict[str, CommonsCandidate]:
        if not titles:
            return {}

        candidates: dict[str, CommonsCandidate] = {}
        for batch_start in range(0, len(titles), 50):
            batch = titles[batch_start : batch_start + 50]
            payload = self._request_json(
                {
                    "action": "query",
                    "titles": "|".join(batch),
                    "prop": "info|imageinfo|categories",
                    "inprop": "url",
                    "iiprop": "url|mime|size|extmetadata",
                    "iiurlwidth": 700,
                    "cllimit": "max",
                }
            )
            for page in payload.get("query", {}).get("pages", []):
                title = str(page.get("title", ""))
                if not title or page.get("missing"):
                    continue
                imageinfo = (page.get("imageinfo") or [{}])[0]
                extmetadata = {}
                for key, value in (imageinfo.get("extmetadata") or {}).items():
                    extmetadata[str(key)] = extmetadata_value({"x": value}, "x")
                candidate = CommonsCandidate(
                    title=title,
                    page_url=page.get("fullurl") or COMMONS_FILE_BASE + urllib.parse.quote(title.replace(" ", "_")),
                    direct_url=imageinfo.get("url", ""),
                    thumb_url=imageinfo.get("thumburl", ""),
                    mime=imageinfo.get("mime", ""),
                    width=imageinfo.get("width"),
                    height=imageinfo.get("height"),
                    categories=[str(cat.get("title", "")) for cat in page.get("categories", [])],
                    extmetadata=extmetadata,
                )
                candidates[title] = candidate
        return candidates


def text_blob(candidate: CommonsCandidate) -> str:
    metadata_values = " ".join(candidate.extmetadata.values())
    return " ".join([candidate.title, candidate.snippet, " ".join(candidate.categories), metadata_values])


def score_candidate(inscription: Inscription, candidate: CommonsCandidate) -> tuple[int, list[str]]:
    """Return confidence score and human-readable reasons."""
    reasons: list[str] = []
    score = 0

    title_fold = fold_text(candidate.title)
    title_compact = compact_fold(candidate.title)
    all_fold = fold_text(text_blob(candidate))
    all_compact = compact_fold(text_blob(candidate))

    sigs = []
    for signature in unique_keep_order([inscription.signature, inscription.canonical_signature]):
        sigs.extend(signature_variants(signature))

    for sig in unique_keep_order(sigs):
        sig_fold = fold_text(sig)
        sig_compact = compact_fold(sig)
        if sig_compact and sig_compact in title_compact:
            score += 80
            reasons.append(f"signature variant in file title: {sig}")
            break
        if sig_fold and re.search(rf"\b{re.escape(sig_fold)}\b", all_fold):
            score += 55
            reasons.append(f"signature variant in metadata/category: {sig}")
            break
        if sig_compact and sig_compact in all_compact:
            score += 40
            reasons.append(f"compact signature variant in metadata/category: {sig}")
            break

    for loc in location_variants(inscription):
        loc_fold = fold_text(loc)
        loc_compact = compact_fold(loc)
        if len(loc_compact) < 4:
            continue
        if loc_compact in title_compact:
            score += 35
            reasons.append(f"location in file title: {loc}")
            break
        if loc_fold and re.search(rf"\b{re.escape(loc_fold)}\b", all_fold):
            score += 20
            reasons.append(f"location in metadata/category: {loc}")
            break

    parish = re.sub(r"\b(?:sn|socken)\b\.?", "", inscription.parish, flags=re.IGNORECASE).strip()
    if parish and compact_fold(parish) in all_compact:
        score += 10
        reasons.append(f"parish match: {parish}")

    municipality = inscription.municipality.strip()
    if municipality and compact_fold(municipality) in all_compact:
        score += 8
        reasons.append(f"municipality match: {municipality}")

    if re.search(r"\b(runestone|rune stone|runsten|runic inscription|rune inscription)\b", all_fold):
        score += 10
        reasons.append("runestone/runic wording")

    if candidate.mime.startswith("image/"):
        score += 5
        reasons.append("Commons file is an image")

    title_category_fold = fold_text(" ".join([candidate.title, *candidate.categories]))
    if re.search(r"\b(miniatyrkopia|kopia|copy|replica|model|reproduction)\b", title_category_fold):
        score -= 35
        reasons.append("possible copy/replica/model penalty")

    # Keep the score readable and stable for review sorting.
    return max(0, min(score, 100)), reasons


def load_inscriptions(
    db_path: Path,
    signatures: Sequence[str] | None = None,
    signature_prefixes: Sequence[str] | None = None,
    limit: int | None = None,
) -> list[Inscription]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    sql = """
        SELECT
            m.id AS meta_id,
            s.signature_text AS signature,
            canonical_signature.signature_text AS canonical_signature,
            m.found_location,
            m.parish,
            m.municipality,
            m.current_location,
            m.original_site
        FROM signatures s
        JOIN signatures canonical_signature ON canonical_signature.id = COALESCE(s.parent_id, s.id)
        JOIN meta_information m ON m.signature_id = canonical_signature.id
    """
    params: list[Any] = []
    where_parts: list[str] = []
    if signatures:
        placeholders = ",".join("?" for _ in signatures)
        where_parts.append(f"s.signature_text IN ({placeholders})")
        params.extend(signatures)
    if signature_prefixes:
        prefix_parts = []
        for prefix in signature_prefixes:
            prefix_parts.append("s.signature_text LIKE ?")
            params.append(f"{prefix}%")
        where_parts.append("(" + " OR ".join(prefix_parts) + ")")
    if not signatures and not signature_prefixes:
        where_parts.append("s.parent_id IS NULL")
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += " ORDER BY s.signature_text"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [
        Inscription(
            meta_id=int(row["meta_id"]),
            signature=str(row["signature"] or ""),
            canonical_signature=str(row["canonical_signature"] or ""),
            found_location=str(row["found_location"] or ""),
            parish=str(row["parish"] or ""),
            municipality=str(row["municipality"] or ""),
            current_location=str(row["current_location"] or ""),
            original_site=str(row["original_site"] or ""),
        )
        for row in rows
    ]


def load_existing_commons_urls(db_path: Path) -> dict[int, set[str]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    existing: dict[int, set[str]] = {}
    for row in conn.execute(
        """
        SELECT meta_id, link_url, direct_url
        FROM runes_imagelink
        WHERE link_url LIKE '%commons.wikimedia.org%'
           OR direct_url LIKE '%commons.wikimedia.org%'
           OR link_url LIKE '%upload.wikimedia.org%'
           OR direct_url LIKE '%upload.wikimedia.org%'
        """
    ):
        urls = existing.setdefault(int(row["meta_id"]), set())
        for key in ("link_url", "direct_url"):
            value = str(row[key] or "")
            if value:
                urls.add(value)
    conn.close()
    return existing


def is_already_in_db(meta_id: int, candidate: CommonsCandidate, existing_urls: dict[int, set[str]]) -> bool:
    urls = existing_urls.get(meta_id, set())
    return bool({candidate.page_url, candidate.direct_url, candidate.thumb_url}.intersection(urls))


def collect_candidates_for_inscription(
    client: CommonsClient,
    inscription: Inscription,
    search_limit: int,
    max_queries: int,
) -> dict[str, CommonsCandidate]:
    titles: dict[str, CommonsCandidate] = {}
    title_snippets: dict[str, str] = {}
    queries = build_search_queries(inscription, max_queries=max_queries)

    for query in queries:
        for title, snippet in client.search_file_titles(query, search_limit):
            if not title.startswith("File:"):
                continue
            title_snippets.setdefault(title, snippet)
            titles.setdefault(title, CommonsCandidate(title=title)).search_queries.add(query)

    detailed = client.fetch_file_details(list(titles))
    for title, candidate in detailed.items():
        if title in titles:
            candidate.search_queries = titles[title].search_queries
            candidate.snippet = title_snippets.get(title, "")
    return detailed


def rank_candidates(
    inscription: Inscription,
    candidates: Iterable[CommonsCandidate],
    existing_urls: dict[int, set[str]],
    min_confidence: int,
    max_per_inscription: int,
) -> list[ScoredCandidate]:
    scored: list[ScoredCandidate] = []
    for candidate in candidates:
        if not candidate.mime.startswith("image/"):
            continue
        confidence, reasons = score_candidate(inscription, candidate)
        if confidence < min_confidence:
            continue
        scored.append(
            ScoredCandidate(
                candidate=candidate,
                confidence=confidence,
                reasons=reasons,
                already_in_db=is_already_in_db(inscription.meta_id, candidate, existing_urls),
            )
        )
    scored.sort(
        key=lambda item: (
            item.confidence,
            "signature variant in file title" in "; ".join(item.reasons),
            item.candidate.title.casefold(),
        ),
        reverse=True,
    )
    return scored[:max_per_inscription]


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    fieldnames = [
        "signature",
        "meta_id",
        "rank",
        "confidence",
        "reasons",
        "already_in_db",
        "commons_file_page",
        "direct_image_url",
        "thumbnail_url",
        "file_title",
        "mime",
        "width",
        "height",
        "license_short_name",
        "license_url",
        "artist",
        "credit",
        "search_queries",
        "info_suggestion",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def export_commons_links(
    db_path: Path,
    out_path: Path,
    signatures: Sequence[str] | None,
    signature_prefixes: Sequence[str] | None,
    inscription_limit: int | None,
    max_per_inscription: int,
    min_confidence: int,
    search_limit: int,
    max_queries: int,
    client: CommonsClient,
) -> tuple[int, int]:
    inscriptions = load_inscriptions(
        db_path,
        signatures=signatures,
        signature_prefixes=signature_prefixes,
        limit=inscription_limit,
    )
    existing_urls = load_existing_commons_urls(db_path)
    output_rows: list[dict[str, Any]] = []

    for index, inscription in enumerate(inscriptions, start=1):
        print(f"[{index}/{len(inscriptions)}] Searching Commons for {inscription.signature}", flush=True)
        candidates = collect_candidates_for_inscription(client, inscription, search_limit, max_queries)
        ranked = rank_candidates(
            inscription,
            candidates.values(),
            existing_urls,
            min_confidence=min_confidence,
            max_per_inscription=max_per_inscription,
        )
        for rank, scored in enumerate(ranked, start=1):
            candidate = scored.candidate
            license_short = candidate.extmetadata.get("LicenseShortName", "")
            license_url = candidate.extmetadata.get("LicenseUrl", "")
            artist = candidate.extmetadata.get("Artist", "")
            credit = candidate.extmetadata.get("Credit", "")
            info_parts = ["Wikimedia Commons"]
            if artist:
                info_parts.append(f"artist: {artist}")
            if license_short:
                info_parts.append(f"license: {license_short}")
            output_rows.append(
                {
                    "signature": inscription.signature,
                    "meta_id": inscription.meta_id,
                    "rank": rank,
                    "confidence": scored.confidence,
                    "reasons": "; ".join(scored.reasons),
                    "already_in_db": "yes" if scored.already_in_db else "no",
                    "commons_file_page": candidate.page_url,
                    "direct_image_url": candidate.direct_url,
                    "thumbnail_url": candidate.thumb_url,
                    "file_title": candidate.title,
                    "mime": candidate.mime,
                    "width": candidate.width or "",
                    "height": candidate.height or "",
                    "license_short_name": license_short,
                    "license_url": license_url,
                    "artist": artist,
                    "credit": credit,
                    "search_queries": " | ".join(sorted(candidate.search_queries)),
                    "info_suggestion": "; ".join(info_parts),
                }
            )

    row_count = write_csv(out_path, output_rows)
    return len(inscriptions), row_count


def parse_signature_file(path: Path | None) -> list[str]:
    if path is None:
        return []
    signatures: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            value = line.strip()
            if value and not value.startswith("#"):
                signatures.append(value)
    return signatures


def unique_prefixes(values: Iterable[str]) -> list[str]:
    """Deduplicate signature prefixes without stripping meaningful spaces."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = str(raw or "")
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export high-confidence Wikimedia Commons image links for Rundata inscriptions."
    )
    parser.add_argument("--db", default="rundatanet/static/runes/runes.sqlite3", help="Path to runes.sqlite3.")
    parser.add_argument("--out", required=True, help="Output CSV path.")
    parser.add_argument("--signatures", nargs="*", help="Optional inscription signatures to export, e.g. 'Öl 1'.")
    parser.add_argument("--signature-file", help="Optional UTF-8 file with one inscription signature per line.")
    parser.add_argument(
        "--signature-prefix",
        nargs="*",
        help="Optional signature prefixes to export, e.g. 'Öl ' for all Öland inscriptions.",
    )
    parser.add_argument("--limit-inscriptions", type=int, help="Optional maximum number of inscriptions to process.")
    parser.add_argument(
        "--max-per-inscription",
        type=int,
        default=DEFAULT_MAX_PER_INSCRIPTION,
        help="Maximum rows to export per inscription. Default: 10.",
    )
    parser.add_argument(
        "--min-confidence",
        type=int,
        default=DEFAULT_MIN_CONFIDENCE,
        help="Minimum confidence score to export. Default: 35.",
    )
    parser.add_argument("--search-limit", type=int, default=20, help="Commons search results per query. Default: 20.")
    parser.add_argument("--max-queries", type=int, default=8, help="Search queries per inscription. Default: 8.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds. Default: 30.")
    parser.add_argument("--delay", type=float, default=0.25, help="Delay between Commons API calls. Default: 0.25.")
    parser.add_argument("--max-retries", type=int, default=4, help="Retries per Commons API request. Default: 4.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent sent to Commons API.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    signatures = unique_keep_order([*(args.signatures or []), *parse_signature_file(Path(args.signature_file) if args.signature_file else None)])
    signature_prefixes = unique_prefixes(args.signature_prefix or [])
    client = CommonsClient(
        timeout=args.timeout,
        delay=args.delay,
        max_retries=args.max_retries,
        user_agent=args.user_agent,
    )
    inscription_count, row_count = export_commons_links(
        db_path=Path(args.db),
        out_path=Path(args.out),
        signatures=signatures or None,
        signature_prefixes=signature_prefixes or None,
        inscription_limit=args.limit_inscriptions,
        max_per_inscription=args.max_per_inscription,
        min_confidence=args.min_confidence,
        search_limit=args.search_limit,
        max_queries=args.max_queries,
        client=client,
    )
    print("COMMONS_EXPORT_REPORT")
    print(f"inscriptions_processed={inscription_count}")
    print(f"rows_written={row_count}")
    print(f"output_csv={Path(args.out)}")


if __name__ == "__main__":
    main()
