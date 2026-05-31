import json
import logging
import re
import unicodedata
from typing import Any, Optional

from azure.core.exceptions import ServiceResponseTimeoutError
from django.conf import settings
from ninja import NinjaAPI, Schema

from .inference import inference
from .models import MetaInformation, Signature
from .normalization import SlugIndex, normalize_signature
from .serializers import MetaInformationSerializer

logger = logging.getLogger(__name__)


def _is_group(node: Any) -> bool:
    return isinstance(node, dict) and isinstance(node.get("rules"), list)


def _iter_rules(node: Any):
    if not _is_group(node):
        return
    for child in node["rules"]:
        if isinstance(child, dict):
            if _is_group(child):
                yield from _iter_rules(child)
            else:
                yield child


def _has_rule(root: dict[str, Any], rule_id: str) -> bool:
    return any(rule.get("id") == rule_id for rule in _iter_rules(root))


def _normalize_str(value: Any) -> str:
    return str(value or "").strip().lower()


def _has_dating_prefix(root: dict[str, Any], prefix: str) -> bool:
    expected = _normalize_str(prefix)
    for rule in _iter_rules(root):
        if rule.get("id") != "dating":
            continue
        if _normalize_str(rule.get("operator")) != "begins_with":
            continue
        if _normalize_str(rule.get("value")) == expected:
            return True
    return False


def _rule_value_contains(rule: dict[str, Any], expected: str) -> bool:
    needle = _normalize_str(expected)
    value = rule.get("value")
    if isinstance(value, list):
        return any(needle in _normalize_str(item) for item in value)
    return needle in _normalize_str(value)


def _has_location_value(root: dict[str, Any], rule_ids: tuple[str, ...], expected: str) -> bool:
    for rule in _iter_rules(root):
        if rule.get("id") not in rule_ids:
            continue
        if _rule_value_contains(rule, expected):
            return True
    return False


def _normalize_root(raw_rules: Any) -> dict[str, Any]:
    if _is_group(raw_rules):
        root = raw_rules
    else:
        root = {"condition": "AND", "rules": [], "not": False}
    root.setdefault("condition", "AND")
    root.setdefault("rules", [])
    root.setdefault("not", False)
    return root


def _append_and_constraint(root: dict[str, Any], constraint: dict[str, Any]) -> dict[str, Any]:
    if str(root.get("condition", "AND")).upper() == "AND":
        root["rules"].append(constraint)
        return root
    return {
        "condition": "AND",
        "rules": [root, constraint],
        "not": False,
        "valid": bool(root.get("valid", True)),
    }


def _make_dating_rule(prefix: str) -> dict[str, Any]:
    return {
        "id": "dating",
        "field": "dating",
        "type": "string",
        "input": "text",
        "operator": "begins_with",
        "value": prefix,
        "ignoreCase": True,
        "includeSpecialSymbols": False,
    }


def _make_current_location_rule(value: str) -> dict[str, Any]:
    return {
        "id": "current_location",
        "field": "current_location",
        "type": "string",
        "input": "text",
        "operator": "contains",
        "value": value,
        "ignoreCase": True,
        "includeSpecialSymbols": False,
    }


def _make_inscription_country_rule(codes: list[str]) -> dict[str, Any]:
    return {
        "id": "inscription_country",
        "field": "signature_text",
        "type": "string",
        "input": "select",
        "operator": "in",
        "value": codes,
        "data": {
            "multiField": True,
        },
    }


def _make_full_address_rule(value: str) -> dict[str, Any]:
    return {
        "id": "full_address",
        "field": "full_address",
        "type": "string",
        "input": "text",
        "operator": "contains",
        "value": value,
        "ignoreCase": True,
        "includeSpecialSymbols": False,
    }


def _clean_location_value(value: str) -> str:
    cleaned = (value or "").strip(" .,!?:;\"'()[]{}")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(
        r"\b(kommun|socken|härad|harad|kyrka|church|county|municipality|parish|district)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or ""))
    without_diacritics = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", without_diacritics).strip().lower()


COUNTRY_PROVINCE_ALIASES: dict[str, str] = {
    # Swedish provinces
    "uppland": "U ",
    "sodermanland": "Sö ",
    "södermanland": "Sö ",
    "ostergotland": "Ög ",
    "östergötland": "Ög ",
    "oland": "Öl ",
    "öland": "Öl ",
    "smaland": "Sm ",
    "småland": "Sm ",
    "vastergotland": "Vg ",
    "västergötland": "Vg ",
    "vastmanland": "Vs ",
    "västmanland": "Vs ",
    "narke": "Nä ",
    "närike": "Nä ",
    "närke": "Nä ",
    "varmland": "Vr ",
    "värmland": "Vr ",
    "gastrikland": "Gs ",
    "gästrikland": "Gs ",
    "halsingland": "Hs ",
    "hälsingland": "Hs ",
    "medelpad": "M ",
    "angermanland": "Ån ",
    "ångermanland": "Ån ",
    "dalarna": "D ",
    "harjedalen": "Hr ",
    "härjedalen": "Hr ",
    "jamtland": "J ",
    "jämtland": "J ",
    "lappland": "Lp ",
    "dalsland": "Ds ",
    "bohuslan": "Bo ",
    "bohuslän": "Bo ",
    "gotland": "G ",
    # Countries/areas
    "sweden": "all_sweden",
    "sverige": "all_sweden",
    "denmark": "DR ",
    "danmark": "DR ",
    "norway": "N ",
    "norge": "N ",
    "faroe islands": "FR ",
    "faroarna": "FR ",
    "färöarna": "FR ",
    "greenland": "GR ",
    "gronland": "GR ",
    "grönland": "GR ",
    "iceland": "IS ",
    "island": "IS ",
    "islande": "IS ",
    "finland": "FI ",
    "shetland": "Sh ",
    "orkney": "Or ",
    "scotland": "Sc ",
    "england": "E ",
    "isle of man": "IM ",
    "ireland": "IR ",
    "france": "F ",
    "netherlands": "NL ",
    "holland": "NL ",
    "germany": "DE ",
    "tyskland": "DE ",
    "poland": "PL ",
    "latvia": "LV ",
    "russia": "RU ",
    "ukraine": "UA ",
    "byzantium": "By ",
    "italy": "IT ",
}


def _extract_inscription_country_codes(user_text: str) -> list[str]:
    folded = _fold_text(user_text)
    found_codes: list[str] = []
    seen = set()
    for alias in sorted(COUNTRY_PROVINCE_ALIASES.keys(), key=len, reverse=True):
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, folded):
            code = COUNTRY_PROVINCE_ALIASES[alias]
            if code not in seen:
                seen.add(code)
                found_codes.append(code)
    return found_codes


def _term_maps_to_country_or_province(value: str) -> bool:
    return _fold_text(value) in COUNTRY_PROVINCE_ALIASES


def _extract_location_terms(user_text: str) -> list[str]:
    text = user_text or ""
    terms: list[str] = []

    # Prefer explicit "found in" style location phrases.
    patterns = [
        r"\b(?:can\s+be\s+found\s+in|found\s+in|located\s+in)\s+([A-Za-zÅÄÖåäöÉéÜü\- ]{2,})",
        r"\b(?:from|in|i|från)\s+([A-Za-zÅÄÖåäöÉéÜü\- ]{2,})",
    ]
    stop_words = {
        "which",
        "that",
        "som",
        "with",
        "med",
        "and",
        "och",
        "period",
        "times",
        "age",
    }
    blocked_location_starts = (
        "viking",
        "vikingatid",
        "medieval",
        "medieaval",
        "medievel",
        "medeltid",
        "proto norse",
        "proto-norse",
        "urnordisk",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            raw = match.group(1).strip()
            token_list = raw.split()
            cut_idx = None
            for idx, token in enumerate(token_list):
                if token.lower() in stop_words:
                    cut_idx = idx
                    break
            if cut_idx is not None:
                raw = " ".join(token_list[:cut_idx])
            cleaned = _clean_location_value(raw)
            if len(cleaned) < 2:
                continue
            if _term_maps_to_country_or_province(cleaned):
                continue
            if any(cleaned.lower().startswith(prefix) for prefix in blocked_location_starts):
                continue
            if cleaned.lower() in {"their", "there", "here", "original", "site", "place"}:
                continue
            if cleaned.lower() not in {term.lower() for term in terms}:
                terms.append(cleaned)
    return terms


def _enforce_inscription_country_codes(root: dict[str, Any], codes: list[str]) -> dict[str, Any]:
    merged_codes = []
    seen = set()
    for code in codes:
        if code not in seen:
            seen.add(code)
            merged_codes.append(code)

    target_rule = None
    for rule in _iter_rules(root):
        if rule.get("id") == "inscription_country":
            target_rule = rule
            break

    if target_rule is None:
        return _append_and_constraint(root, _make_inscription_country_rule(merged_codes))

    existing_value = target_rule.get("value")
    if isinstance(existing_value, list):
        for code in existing_value:
            if code not in seen:
                seen.add(code)
                merged_codes.append(code)
    elif existing_value:
        code = str(existing_value)
        if code not in seen:
            seen.add(code)
            merged_codes.append(code)

    target_rule.update(_make_inscription_country_rule(merged_codes))
    return root


def _enforce_dating_prefix(root: dict[str, Any], prefix: str) -> dict[str, Any]:
    found_any = False
    for rule in _iter_rules(root):
        if rule.get("id") != "dating":
            continue
        found_any = True
        rule.update(_make_dating_rule(prefix))
    if not found_any:
        root = _append_and_constraint(root, _make_dating_rule(prefix))
    return root


def _postprocess_ai_rules(user_text: str, llm_rules_json: str) -> str:
    """
    Deterministic safety net for high-value intent that should never be dropped
    by the model in mixed-constraint queries.
    """
    try:
        parsed = json.loads(llm_rules_json)
    except Exception:
        return llm_rules_json

    root = _normalize_root(parsed)
    text = (user_text or "").lower()

    dating_prefix = None
    if re.search(r"\b(viking|vikingatid)\w*\b", text):
        dating_prefix = "V"
    elif re.search(r"\b(proto[-\s]?norse|urnordisk)\w*\b", text):
        dating_prefix = "U"
    elif re.search(r"\b(medieval|medieaval|medievel|medeltid)\w*\b", text):
        dating_prefix = "M"

    if dating_prefix and not _has_dating_prefix(root, dating_prefix):
        root = _enforce_dating_prefix(root, dating_prefix)

    if re.search(r"\bshm\b|statens historiska museum", text) and not _has_location_value(
        root, ("current_location", "full_address"), "shm"
    ):
        root = _append_and_constraint(root, _make_current_location_rule("SHM"))

    country_codes = _extract_inscription_country_codes(user_text)
    if country_codes:
        root = _enforce_inscription_country_codes(root, country_codes)

    for location_term in _extract_location_terms(user_text):
        if location_term.lower() == "shm":
            continue
        if not _has_location_value(
            root,
            ("full_address", "current_location", "found_location", "parish", "district", "municipality"),
            location_term,
        ):
            root = _append_and_constraint(root, _make_full_address_rule(location_term))

    root.setdefault("valid", True)
    return json.dumps(root, ensure_ascii=False)


def _build_rules_fallback_from_text(user_text: str) -> Optional[str]:
    """
    Lightweight deterministic fallback used when LLM inference fails.
    Returns a valid QueryBuilder JSON string when at least one known intent
    can be mapped; otherwise returns None.
    """
    text = (user_text or "").lower()
    rules: list[dict[str, Any]] = []

    dating_prefix = None
    if re.search(r"\b(viking|vikingatid)\w*\b", text):
        dating_prefix = "V"
    elif re.search(r"\b(proto[-\s]?norse|urnordisk)\w*\b", text):
        dating_prefix = "U"
    elif re.search(r"\b(medieval|medieaval|medievel|medeltid)\w*\b", text):
        dating_prefix = "M"

    if dating_prefix:
        rules.append(_make_dating_rule(dating_prefix))

    if re.search(r"\bshm\b|statens historiska museum", text):
        rules.append(_make_current_location_rule("SHM"))

    country_codes = _extract_inscription_country_codes(user_text)
    if country_codes:
        rules.append(_make_inscription_country_rule(country_codes))

    for location_term in _extract_location_terms(user_text):
        if location_term.lower() == "shm":
            continue
        rules.append(_make_full_address_rule(location_term))

    if not rules:
        return None

    root = {
        "condition": "AND",
        "rules": rules,
        "not": False,
        "valid": True,
    }
    return json.dumps(root, ensure_ascii=False)


def _is_simple_deterministic_query(user_text: str, fallback_rules: Optional[str]) -> bool:
    """
    Detect short, high-confidence intent that can be answered without LLM.
    This avoids unnecessary model latency/timeouts for simple period+SHM style requests.
    """
    if not fallback_rules:
        return False

    text = (user_text or "").lower()
    # If the query contains additional advanced intents, let LLM handle composition.
    advanced_markers = (
        "rune",
        "bind",
        "stung",
        "kortkvist",
        "långkvist",
        "material",
        "object",
        "dating",
        "year",
        "style",
        "carver",
        "parish",
        "district",
        "municipality",
        "country",
        "translation",
        "name",
        "lost",
    )
    return not any(marker in text for marker in advanced_markers)

api = NinjaAPI(
    title="Rundata API",
    version="1.0.0",
    description=(
        "REST API for the Rundata runic inscription database. "
        "Provides endpoints for searching inscriptions, retrieving detailed metadata, "
        "and converting free-form text to normalized runic rules."
    ),
)


class TextRequest(Schema):
    text: str


class TextResponse(Schema):
    rules: str
    error: Optional[str] = None


class InscriptionResponse(Schema):
    signature: str
    canonical_slug: str
    aliases: list[str]
    meta: dict[str, Any]


class SearchOption(Schema):
    id: str
    title: str
    slug: str


class ErrorResponse(Schema):
    detail: str


@api.post("/txt2rules", response=TextResponse, tags=["Rules"])
def txt2rules(request, data: TextRequest):
    """
    Convert free-form text to normalized runic rules.

    Submits a plain-text description to the inference engine, which returns
    a structured rules string suitable for use in inscription searches.

    Returns an empty `rules` string and a populated `error` field if the
    inference step fails.
    """
    try:
        fallback_rules = _build_rules_fallback_from_text(data.text)
        if _is_simple_deterministic_query(data.text, fallback_rules):
            logger.info("Using deterministic preflight rules for simple query.")
            return TextResponse(rules=fallback_rules or "")

        # Call the inference function to get the rules
        llm_response = inference(data.text)
        if llm_response and llm_response.strip():
            llm_response = _postprocess_ai_rules(data.text, llm_response)
            resp = TextResponse(rules=llm_response)
        else:
            if fallback_rules:
                logger.warning("LLM returned empty rules; using deterministic fallback.")
                resp = TextResponse(rules=fallback_rules)
            else:
                resp = TextResponse(rules="", error="Failed to convert text to rules")
    except ServiceResponseTimeoutError as e:
        logger.warning("Timed out while converting text to rules: %s", str(e), exc_info=True)
        fallback_rules = _build_rules_fallback_from_text(data.text)
        if fallback_rules:
            logger.warning("Using deterministic fallback after AI timeout.")
            resp = TextResponse(rules=fallback_rules)
        else:
            resp = TextResponse(
                rules="",
                error="AI request timed out after 20 seconds. Please try again, or simplify the query."
            )
    except Exception as e:
        # Handle the exception and return an error response
        logger.error(f"Error converting text to rules: {str(e)}", exc_info=True)
        fallback_rules = _build_rules_fallback_from_text(data.text)
        if fallback_rules:
            logger.warning("Using deterministic fallback after AI error.")
            resp = TextResponse(rules=fallback_rules)
        else:
            resp = TextResponse(rules="", error="Failed to convert text to rules")
    return resp


@api.get(
    "/search_options",
    response=list[SearchOption],
    tags=["Inscriptions"],
)
def search_options_api(request):
    """
    List all searchable inscription signatures.

    Returns every canonical runic signature as a lightweight option object
    containing an `id`, human-readable `title`, and URL-safe `slug`.
    Intended for populating client-side search datalists and autocomplete widgets.
    Results are sorted alphabetically by signature text.
    """
    index = SlugIndex.get()
    index._ensure_built()

    signatures = Signature.objects.filter(id__in=index._id_to_slug.keys()).values_list("id", "signature_text")

    options = [
        SearchOption(
            id=signature_text,
            title=signature_text,
            slug=index._id_to_slug[sig_id],
        )
        for sig_id, signature_text in signatures
        if sig_id in index._id_to_slug
    ]

    return sorted(options, key=lambda option: option.title)


@api.get(
    "/inscription/{slug}",
    response={200: InscriptionResponse, 404: ErrorResponse},
    tags=["Inscriptions"],
)
def inscription_detail_api(request, slug: str):
    """
    Retrieve full metadata for a single inscription by slug.

    Looks up an inscription using its URL-safe slug. Alias slugs (variant
    identifiers pointing to the same physical inscription) are resolved
    transparently to the canonical record.

    Returns the canonical signature text, canonical slug, a list of known
    alias signatures, and a full metadata object including material type,
    images, and references.

    Responds with **404** if the slug does not match any known inscription
    or if the associated metadata record is missing.
    """
    index = SlugIndex.get()
    result = index.resolve(slug)

    if result is None:
        return 404, {"detail": "Inscription not found"}

    canonical_id, canonical_slug = result

    try:
        signature = Signature.objects.get(id=canonical_id)
    except Signature.DoesNotExist:
        return 404, {"detail": "Inscription not found"}

    try:
        meta = (
            MetaInformation.objects.select_related("signature", "materialType")
            .prefetch_related("images", "references")
            .get(signature=signature)
        )
    except MetaInformation.DoesNotExist:
        return 404, {"detail": "Inscription metadata not found"}

    serializer = MetaInformationSerializer(meta)

    aliases = list(Signature.objects.filter(parent=signature).values_list("signature_text", flat=True))

    return 200, {
        "signature": signature.signature_text,
        "canonical_slug": canonical_slug,
        "aliases": aliases,
        "meta": serializer.data,
    }
