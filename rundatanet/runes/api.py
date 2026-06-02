import json
import logging
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from typing import Any, Optional

from azure.core.exceptions import ServiceResponseTimeoutError
from django.conf import settings
from django.db.models import Q
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


def _make_contains_rule(rule_id: str, field: str, value: str) -> dict[str, Any]:
    return {
        "id": rule_id,
        "field": field,
        "type": "string",
        "input": "text",
        "operator": "contains",
        "value": value,
        "ignoreCase": True,
        "includeSpecialSymbols": False,
    }


def _make_lost_rule(value: int) -> dict[str, Any]:
    return {
        "id": "lost",
        "field": "lost",
        "type": "integer",
        "input": "radio",
        "operator": "equal",
        "value": int(value),
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


def _compact_code(value: str) -> str:
    folded = _fold_text(value)
    return re.sub(r"[^a-z0-9]+", "", folded)


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
        "during",
        "under",
        "i",
        "in",
        "from",
        "period",
        "times",
        "age",
        "viking",
        "vikingatid",
        "medieval",
        "medieaval",
        "medievel",
        "medeltid",
        "proto-norse",
        "proto",
        "norse",
        "urnordisk",
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
            # If a generic capture includes an inner "from/från", keep the trailing place.
            raw = re.split(r"\b(?:från|from)\b", raw, flags=re.IGNORECASE)[-1].strip()
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
            if re.fullmatch(r"(?i)pr(?:\s*\d+)?", cleaned):
                continue
            if re.fullmatch(r"(?i)fp", cleaned):
                continue
            if re.fullmatch(r"(?i)(rak|kb|sod)(?:\s+style)?", cleaned):
                continue
            if _term_maps_to_country_or_province(cleaned):
                continue
            if any(cleaned.lower().startswith(prefix) for prefix in blocked_location_starts):
                continue
            if _fold_text(cleaned) in {"ben", "bone", "metal", "metall"}:
                continue
            if cleaned.lower() in {"their", "there", "here", "original", "site", "place"}:
                continue
            if cleaned.lower() not in {term.lower() for term in terms}:
                terms.append(cleaned)
    return terms


def _extract_specific_location_constraints(user_text: str) -> list[dict[str, str]]:
    text = user_text or ""
    constraints: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    patterns = [
        ("parish", "parish", r"\b(?:parish|socken)\s+([A-Za-zÅÄÖåäöÉéÜü\- ]{2,})"),
        ("district", "district", r"\b(?:district|härad|harad)\s+([A-Za-zÅÄÖåäöÉéÜü\- ]{2,})"),
        ("municipality", "municipality", r"\b(?:municipality|kommun)\s+([A-Za-zÅÄÖåäöÉéÜü\- ]{2,})"),
    ]
    stop_words = {
        "which",
        "that",
        "som",
        "with",
        "med",
        "and",
        "och",
        "during",
        "under",
        "period",
        "times",
        "age",
        "viking",
        "vikingatid",
        "medieval",
        "medieaval",
        "medievel",
        "medeltid",
        "proto-norse",
        "proto",
        "norse",
        "urnordisk",
    }
    for rule_id, field, pattern in patterns:
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
            key = (rule_id, cleaned.lower())
            if key in seen:
                continue
            seen.add(key)
            constraints.append({"id": rule_id, "field": field, "value": cleaned})
    return constraints


def _extract_lost_constraint(user_text: str) -> Optional[int]:
    text = (user_text or "").lower()
    if re.search(r"\b(not\s+lost|inte\s+förlorad|inte\s+forlorad|not\s+missing|bevarad)\b", text):
        return 0
    if re.search(r"\b(lost|missing|förlorad|forlorad)\b", text):
        return 1
    return None


def _extract_material_constraints(user_text: str) -> list[dict[str, str]]:
    text = _fold_text(user_text or "")
    constraints: list[dict[str, str]] = []
    seen_values: set[str] = set()

    def add_material(value: str) -> None:
        if value in seen_values:
            return
        seen_values.add(value)
        constraints.append({"id": "material_type", "field": "material_type", "value": value})

    # Map user wording (Swedish/English) to canonical DB material_type values.
    if re.search(r"\b(stone|sten)\b", text):
        add_material("stone")
    if re.search(r"\b(bone|antler|ben|horn)\b", text):
        add_material("bone/antler")
    if re.search(r"\b(plaster|puts)\b", text):
        add_material("plaster")
    if re.search(r"\b(wood|wooden|tra|trä|timber)\b", text):
        add_material("wood")
    if re.search(r"\b(other|ovrigt|övrigt)\b", text):
        add_material("other")
    if re.search(r"\b(metal|metall)\b", text):
        add_material("metal")
    if re.search(r"\b(unknown|okand|okänd)\b", text):
        add_material("unknown")

    return constraints


def _extract_object_info_constraints(user_text: str) -> list[dict[str, str]]:
    text = _fold_text(user_text or "")
    constraints: list[dict[str, str]] = []
    seen_values: set[str] = set()

    def add_object(value: str) -> None:
        if value in seen_values:
            return
        seen_values.add(value)
        constraints.append({"id": "objectInfo", "field": "objectInfo", "value": value})

    # English/Swedish intent mapping to canonical objectInfo values.
    pattern_map: list[tuple[str, str]] = [
        (r"\b(coin|coins|mynt)\b", "mynt"),
        (r"\b(runestone|runestones|runsten|runstenar)\b", "runsten"),
        (r"\b(grave slab|grave slabs|gravhall|gravhallar|gravhäll|gravhällar)\b", "gravhäll"),
        (r"\b(baptismal font|baptism|dopfunt|dopfund)\b", "dopfunt"),
        (r"\b(bracteate|bracteates|brakteat)\b", "brakteat"),
        (r"\b(amulet|amulets|amulett|amulett?er)\b", "amulett"),
        (r"\b(metal plate|metal plates|bleck)\b", "bleck"),
        (r"\b(stone cross|stenkors)\b", "stenkors"),
        (r"\b(cross|kors)\b", "kors"),
        (r"\b(whetstone|bryne)\b", "bryne"),
        (r"\b(knife handle|knivskaft)\b", "knivskaft"),
        (r"\b(wall inscription|wall graffiti|vagginskrift|vägginskrift|kyrkografitti)\b", "vägginskrift"),
        (r"\b(rock face|rock carving|berghall|berghäll|bergvagg|bergvägg)\b", "berghäll"),
        (r"\b(runic bone|runben)\b", "runben"),
        (r"\b(runic staff|runic stick|runkavel)\b", "runkavel"),
        (r"\b(wooden inscription|trainskrift|träinskrift)\b", "träinskrift"),
        (r"\b(plaster inscription|putsinskrift)\b", "putsinskrift"),
        (r"\b(bell|kyrkklocka)\b", "kyrkklocka"),
        (r"\b(tag|label|marklapp|märklapp)\b", "märklapp"),
    ]
    for pattern, canonical in pattern_map:
        if re.search(pattern, text):
            add_object(canonical)

    # Exact phrase match against all objectInfo values present in DB.
    # This makes all existing objectInfo denominations searchable/combinable
    # when users type the Swedish term directly.
    for value, folded_value in _get_object_info_values():
        if len(folded_value) < 3:
            continue
        if re.search(rf"(^|\b){re.escape(folded_value)}(\b|$)", text):
            add_object(value)

    return constraints


def _extract_style_constraints(user_text: str) -> list[dict[str, str]]:
    constraints: list[dict[str, str]] = []
    seen: set[str] = set()

    def add_style(value: str) -> None:
        normalized_value = re.sub(r"\s+", " ", value.replace("\u00a0", " ")).strip()
        key = _fold_text(normalized_value)
        if key in seen:
            return
        seen.add(key)
        constraints.append({"id": "style", "field": "style", "value": normalized_value})

    for match in re.finditer(r"\bpr(?:ofil|ofile|file|of)?\.?\s*([0-9]+)\b", user_text or "", flags=re.IGNORECASE):
        add_style(f"Pr {match.group(1)}")
    for match in re.finditer(r"\bfp\b|\bfågelperspektiv\b|\bfagelperspektiv\b|\bbird'?s?-eye view\b", user_text or "", flags=re.IGNORECASE):
        add_style("Fp")
    for match in re.finditer(r"\brak\b|\bkb\b|\bsod\b", user_text or "", flags=re.IGNORECASE):
        add_style(match.group(0))

    text_folded = _fold_text(user_text or "")
    for value, folded_value in _get_style_values():
        if len(folded_value) < 2:
            continue
        if re.search(rf"(^|\b){re.escape(folded_value)}(\b|$)", text_folded):
            add_style(value)
    return constraints


@lru_cache(maxsize=1)
def _get_style_values() -> tuple[tuple[str, str], ...]:
    values = (
        MetaInformation.objects.exclude(style__isnull=True)
        .exclude(style__exact="")
        .values_list("style", flat=True)
        .distinct()
    )
    cleaned_pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").replace("\u00a0", " ").strip()
        if not value:
            continue
        # Only expose concise style codes for direct deterministic matching.
        if not re.fullmatch(r"(?i)(rak|fp|kb|sod|pr\s*\d+)", value):
            continue
        folded = _fold_text(value)
        if not folded or folded in seen:
            continue
        seen.add(folded)
        cleaned_pairs.append((value, folded))
    cleaned_pairs.sort(key=lambda item: len(item[1]), reverse=True)
    return tuple(cleaned_pairs)


def _clean_carver_value(value: str) -> str:
    cleaned = (value or "").strip(" .,!?:;\"'()[]{}")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Stop at the next independent constraint phrase.
    cleaned = re.split(
        r"\b(?:in|i|from|från|under|during|with|med|period|dating|style|stil|pr(?:ofil|ofile|file|of)?\.?\s*\d+)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" .,!?:;\"'()[]{}")
    return cleaned


def _extract_carver_constraints(user_text: str) -> list[dict[str, str]]:
    text = user_text or ""
    constraints: list[dict[str, str]] = []
    seen: set[str] = set()
    patterns = [
        r"\b(?:made|carved|cut|ristad|ristade|ristat|gjord|gjorda)\s+by\s+([A-Za-zÅÄÖåäöÉéÜü.\- ]{2,})",
        r"\b(?:made\s+by|carved\s+by|cut\s+by)\s+([A-Za-zÅÄÖåäöÉéÜü.\- ]{2,})",
        r"\b(?:av|by)\s+([A-ZÅÄÖÜÉ][A-Za-zÅÄÖåäöÉéÜü.\- ]{1,})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            value = _clean_carver_value(match.group(1))
            if len(value) < 2:
                continue
            folded = _fold_text(value)
            if folded in {"alla", "all", "inscriptions", "inskrifter", "these", "dessa"}:
                continue
            if folded in seen:
                continue
            seen.add(folded)
            constraints.append({"id": "carver", "field": "carver", "value": value})
    return constraints


@lru_cache(maxsize=1)
def _get_object_info_values() -> tuple[tuple[str, str], ...]:
    values = (
        MetaInformation.objects.exclude(objectInfo__isnull=True)
        .exclude(objectInfo__exact="")
        .values_list("objectInfo", flat=True)
        .distinct()
    )
    cleaned_pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            continue
        folded = _fold_text(value)
        if folded in seen:
            continue
        seen.add(folded)
        cleaned_pairs.append((value, folded))
    # Longest phrases first to prefer specific denominations over short generic ones.
    cleaned_pairs.sort(key=lambda item: len(item[1]), reverse=True)
    return tuple(cleaned_pairs)


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

    for item in _extract_specific_location_constraints(user_text):
        if not _has_location_value(root, (item["id"],), item["value"]):
            root = _append_and_constraint(root, _make_contains_rule(item["id"], item["field"], item["value"]))

    for item in _extract_material_constraints(user_text):
        if not _has_location_value(root, (item["id"],), item["value"]):
            root = _append_and_constraint(root, _make_contains_rule(item["id"], item["field"], item["value"]))

    for item in _extract_object_info_constraints(user_text):
        if not _has_location_value(root, (item["id"],), item["value"]):
            root = _append_and_constraint(root, _make_contains_rule(item["id"], item["field"], item["value"]))

    for item in _extract_style_constraints(user_text):
        if not _has_location_value(root, (item["id"],), item["value"]):
            root = _append_and_constraint(root, _make_contains_rule(item["id"], item["field"], item["value"]))

    for item in _extract_carver_constraints(user_text):
        if not _has_location_value(root, (item["id"],), item["value"]):
            root = _append_and_constraint(root, _make_contains_rule(item["id"], item["field"], item["value"]))

    for location_term in _extract_location_terms(user_text):
        if location_term.lower() == "shm":
            continue
        if not _has_location_value(
            root,
            ("full_address", "current_location", "found_location", "parish", "district", "municipality"),
            location_term,
        ):
            root = _append_and_constraint(root, _make_full_address_rule(location_term))

    lost_value = _extract_lost_constraint(user_text)
    if lost_value is not None and not _has_rule(root, "lost"):
        root = _append_and_constraint(root, _make_lost_rule(lost_value))

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

    for item in _extract_specific_location_constraints(user_text):
        rules.append(_make_contains_rule(item["id"], item["field"], item["value"]))

    for item in _extract_material_constraints(user_text):
        rules.append(_make_contains_rule(item["id"], item["field"], item["value"]))

    for item in _extract_object_info_constraints(user_text):
        rules.append(_make_contains_rule(item["id"], item["field"], item["value"]))

    for item in _extract_style_constraints(user_text):
        rules.append(_make_contains_rule(item["id"], item["field"], item["value"]))

    for item in _extract_carver_constraints(user_text):
        rules.append(_make_contains_rule(item["id"], item["field"], item["value"]))

    for location_term in _extract_location_terms(user_text):
        if location_term.lower() == "shm":
            continue
        rules.append(_make_full_address_rule(location_term))

    lost_value = _extract_lost_constraint(user_text)
    if lost_value is not None:
        rules.append(_make_lost_rule(lost_value))

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


class AiAnswerResponse(Schema):
    answer: str
    matched_inscriptions: int
    metadata: dict[str, Any]
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


SWEDISH_PROVINCE_CODES = [
    "Öl ",
    "Ög ",
    "Sö ",
    "Sm ",
    "Vg ",
    "U ",
    "Vs ",
    "Nä ",
    "Vr ",
    "Gs ",
    "Hs ",
    "M ",
    "Ån ",
    "D ",
    "Hr ",
    "J ",
    "Lp ",
    "Ds ",
    "Bo ",
    "G ",
    "SE ",
]


def _country_codes_to_signature_q(codes: list[str]) -> Optional[Q]:
    if not codes:
        return None
    normalized_codes: list[str] = []
    for code in codes:
        if code == "all_sweden":
            normalized_codes.extend(SWEDISH_PROVINCE_CODES)
        else:
            normalized_codes.append(code)

    query = Q()
    for code in sorted(set(normalized_codes)):
        query |= Q(signature__signature_text__startswith=code)
    return query if query.children else None


def _extract_unique_carvers(carver_value: str) -> list[str]:
    if not carver_value:
        return []
    parts = re.split(r"[;,/&]| och | and ", carver_value, flags=re.IGNORECASE)
    result: list[str] = []
    seen: set[str] = set()
    ignored = {"", "-", "?", "okänd", "okand", "unknown", "anonym", "anonymous"}
    for part in parts:
        cleaned = re.sub(r"\s+", " ", str(part).strip(" .,!?:;\"'()[]{}"))
        if not cleaned:
            continue
        folded = _fold_text(cleaned)
        if folded in ignored or len(folded) < 2:
            continue
        if folded not in seen:
            seen.add(folded)
            result.append(cleaned)
    return result


def _build_location_q(user_text: str) -> Optional[Q]:
    query = Q()
    has_any = False

    for item in _extract_specific_location_constraints(user_text):
        has_any = True
        query &= Q(**{f"{item['field']}__icontains": item["value"]})

    for term in _extract_location_terms(user_text):
        if term.lower() == "shm":
            has_any = True
            query &= Q(current_location__icontains="SHM")
            continue
        has_any = True
        query &= (
            Q(found_location__icontains=term)
            | Q(parish__icontains=term)
            | Q(district__icontains=term)
            | Q(municipality__icontains=term)
            | Q(current_location__icontains=term)
        )

    return query if has_any else None


def _build_meta_queryset_from_text(user_text: str, *, ignore_dating_constraint: bool = False):
    qs = MetaInformation.objects.select_related(
        "signature",
        "materialType",
        "signature__normalisation_norse",
        "signature__normalisation_scandinavian",
        "signature__transliteration",
    )

    text = (user_text or "").lower()
    dating_prefix = None
    if re.search(r"\b(viking|vikingatid)\w*\b", text):
        dating_prefix = "V"
    elif re.search(r"\b(proto[-\s]?norse|urnordisk)\w*\b", text):
        dating_prefix = "U"
    elif re.search(r"\b(medieval|medieaval|medievel|medeltid)\w*\b", text):
        dating_prefix = "M"
    if dating_prefix and not ignore_dating_constraint:
        qs = qs.filter(dating__istartswith=dating_prefix)

    lost_value = _extract_lost_constraint(user_text)
    if lost_value is not None:
        qs = qs.filter(lost=bool(lost_value))

    country_codes = _extract_inscription_country_codes(user_text)
    country_q = _country_codes_to_signature_q(country_codes)
    if country_q is not None:
        qs = qs.filter(country_q)

    location_q = _build_location_q(user_text)
    if location_q is not None:
        qs = qs.filter(location_q)

    for material in _extract_material_constraints(user_text):
        # material_type is modeled as FK to MaterialType.name in ORM.
        qs = qs.filter(materialType__name__iexact=material["value"])

    for item in _extract_object_info_constraints(user_text):
        qs = qs.filter(objectInfo__icontains=item["value"])

    for item in _extract_style_constraints(user_text):
        qs = qs.filter(style__icontains=item["value"])

    for item in _extract_carver_constraints(user_text):
        qs = qs.filter(carver__icontains=item["value"])

    return qs, dating_prefix, country_codes


def _extract_requested_period_codes(user_text: str) -> list[str]:
    text = _fold_text(user_text or "")
    requested: list[str] = []
    seen: set[str] = set()

    def add(code: str) -> None:
        if code not in seen:
            seen.add(code)
            requested.append(code)

    if re.search(r"\bproto[-\s]?norse\b|\burnordisk\b", text):
        add("U")
    if re.search(r"\bviking\b|\bvikingatid\b", text):
        add("V")
    if re.search(r"\bmedieval\b|\bmedieaval\b|\bmedievel\b|\bmedeltid\b", text):
        add("M")
    if re.search(r"\bu\b", text):
        add("U")
    if re.search(r"\bv\b", text):
        add("V")
    if re.search(r"\bm\b", text):
        add("M")

    if requested:
        return requested
    return ["U", "V", "M"]


def _is_effective_text(value: Optional[str]) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    folded = _fold_text(raw)
    return folded not in {"", "...", "…", "-", "?", "okand", "okänd", "unknown"}


def _is_uninterpreted(meta: MetaInformation) -> bool:
    signature = meta.signature
    norm_norse_value = ""
    norm_scand_value = ""
    translit_value = ""
    try:
        norm_norse_value = signature.normalisation_norse.value
    except Exception:
        norm_norse_value = ""
    try:
        norm_scand_value = signature.normalisation_scandinavian.value
    except Exception:
        norm_scand_value = ""
    try:
        translit_value = signature.transliteration.value
    except Exception:
        translit_value = ""

    has_normalization = _is_effective_text(norm_norse_value) or _is_effective_text(norm_scand_value)
    has_transliteration = _is_effective_text(translit_value)
    # User-defined rule: inscription is uninterpreted if either normalization
    # or transliteration is missing.
    return not (has_normalization and has_transliteration)


def _answer_how_many_carvers(user_text: str) -> AiAnswerResponse:
    qs, dating_prefix, country_codes = _build_meta_queryset_from_text(user_text)

    unique_carvers: set[str] = set()
    display_examples: list[str] = []
    matched_inscriptions = 0

    for meta in qs.iterator():
        matched_inscriptions += 1
        parsed = _extract_unique_carvers(meta.carver or "")
        for name in parsed:
            folded = _fold_text(name)
            if folded not in unique_carvers:
                unique_carvers.add(folded)
                if len(display_examples) < 12:
                    display_examples.append(name)

    if matched_inscriptions == 0:
        return AiAnswerResponse(
            answer="I found 0 inscriptions matching this question, so the number of identified carvers is 0.",
            matched_inscriptions=0,
            metadata={
                "unique_carver_count": 0,
                "carver_examples": [],
                "country_codes": country_codes,
                "dating_prefix": dating_prefix,
            },
        )

    unique_count = len(unique_carvers)
    answer = (
        f"I found {unique_count} distinct carvers in {matched_inscriptions} matching inscriptions. "
        f"Examples: {', '.join(display_examples) if display_examples else 'no named carvers in these matches'}."
    )
    return AiAnswerResponse(
        answer=answer,
        matched_inscriptions=matched_inscriptions,
        metadata={
            "unique_carver_count": unique_count,
            "carver_examples": display_examples,
            "country_codes": country_codes,
            "dating_prefix": dating_prefix,
        },
    )


def _answer_uninterpreted_inscriptions(user_text: str) -> AiAnswerResponse:
    qs, dating_prefix, country_codes = _build_meta_queryset_from_text(user_text)
    all_matches = list(qs.iterator())
    matched_inscriptions = len(all_matches)
    uninterpreted = [meta for meta in all_matches if _is_uninterpreted(meta)]
    uninterpreted_count = len(uninterpreted)
    signatures = sorted({meta.signature.signature_text for meta in uninterpreted})

    if matched_inscriptions == 0:
        return AiAnswerResponse(
            answer="I found 0 inscriptions matching your filters, so 0 are uninterpreted.",
            matched_inscriptions=0,
            metadata={
                "uninterpreted_count": 0,
                "signatures": [],
                "country_codes": country_codes,
                "dating_prefix": dating_prefix,
            },
        )

    if uninterpreted_count == 0:
        return AiAnswerResponse(
            answer=(
                f"I found {matched_inscriptions} matching inscriptions. "
                "None of them are uninterpreted (all have normalization or transliteration)."
            ),
            matched_inscriptions=matched_inscriptions,
            metadata={
                "uninterpreted_count": 0,
                "signatures": [],
                "country_codes": country_codes,
                "dating_prefix": dating_prefix,
            },
        )

    max_list = 200
    truncated = len(signatures) > max_list
    shown = signatures[:max_list]
    answer = (
        f"I found {matched_inscriptions} matching inscriptions. "
        f"{uninterpreted_count} of them are uninterpreted "
        "(missing normalization or transliteration). "
        f"Signatures: {', '.join(shown)}"
    )
    if truncated:
        answer += f" (showing first {max_list} of {len(signatures)})."

    return AiAnswerResponse(
        answer=answer,
        matched_inscriptions=matched_inscriptions,
        metadata={
            "uninterpreted_count": uninterpreted_count,
            "signatures": shown,
            "all_signatures_count": len(signatures),
            "country_codes": country_codes,
            "dating_prefix": dating_prefix,
        },
    )


def _looks_like_carver_count_question(user_text: str) -> bool:
    text = _fold_text(user_text or "")
    return (
        ("carver" in text or "ristare" in text)
        and ("how many" in text or "antal" in text or "hur manga" in text or "count" in text)
    )


def _looks_like_uninterpreted_question(user_text: str) -> bool:
    text = _fold_text(user_text or "")
    asks_how_many = any(phrase in text for phrase in ("how many", "hur manga", "antal"))
    asks_uninterpreted = any(
        phrase in text for phrase in ("uninterpreted", "not interpreted", "otolkade", "otolkad", "tolkade")
    )
    asks_which = any(phrase in text for phrase in ("which", "vilka", "what are"))
    return asks_uninterpreted and (asks_how_many or asks_which)


def _extract_signature_candidates(user_text: str) -> list[str]:
    text = user_text or ""
    # Broad candidate matcher; real validation happens via SlugIndex.resolve.
    pattern = r"\b[A-Za-zÅÄÖåäö]{1,4}\s*[A-Za-z0-9;:.\-]+\b"
    candidates: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(pattern, text):
        raw = match.group(0).strip().strip(",.;:!?")
        if not any(ch.isdigit() for ch in raw):
            continue
        candidate = re.sub(r"\s+", " ", raw).strip()
        folded = _fold_text(candidate)
        if folded in seen:
            continue
        seen.add(folded)
        candidates.append(candidate)
    return candidates


def _looks_like_similarity_question(user_text: str) -> bool:
    text = _fold_text(user_text or "")
    asks_similarity = any(token in text for token in ("gemensamt", "common", "similarit", "likheter"))
    return asks_similarity and len(_extract_signature_candidates(user_text)) >= 2


def _looks_like_similarity_over_filters_question(user_text: str) -> bool:
    text = _fold_text(user_text or "")
    asks_similarity = any(token in text for token in ("gemensamt", "common", "similarit", "likheter", "jamfor", "jämför"))
    asks_plural_set = any(token in text for token in ("all inscriptions", "alla inskrifter", "these inscriptions", "dessa"))
    has_explicit_list = len(_extract_signature_candidates(user_text)) >= 2
    return asks_similarity and asks_plural_set and not has_explicit_list


def _compute_similarity_patterns(
    ordered_pairs: list[tuple[str, MetaInformation]], field_specs: list[tuple[str, Any]]
) -> tuple[list[str], list[str]]:
    shared_exact: list[str] = []
    frequent_patterns: list[str] = []
    n = len(ordered_pairs)
    threshold = max(2, int((n * 2) / 3 + 0.999))  # ceil(2/3 * n)

    for label, getter in field_specs:
        values = []
        for _, meta in ordered_pairs:
            value = str(getter(meta) or "").strip()
            if value:
                values.append(value)
        if len(values) != n:
            if not values:
                continue
        normalized = [_fold_text(v) for v in values]
        if len(values) == n and len(set(normalized)) == 1:
            shared_exact.append(f"{label}: {values[0]}")
            continue

        counts = Counter(normalized)
        top_norm, top_count = counts.most_common(1)[0]
        if top_count >= threshold:
            display_value = next(v for v in values if _fold_text(v) == top_norm)
            frequent_patterns.append(f"{label}: {display_value} ({top_count}/{n})")

    return shared_exact, frequent_patterns


def _answer_signature_similarity(user_text: str) -> AiAnswerResponse:
    candidates = _extract_signature_candidates(user_text)
    index = SlugIndex.get()
    resolved_ids: list[int] = []
    seen_ids: set[int] = set()
    unresolved: list[str] = []
    for candidate in candidates:
        resolved = index.resolve(candidate)
        if not resolved:
            unresolved.append(candidate)
            continue
        sig_id, _ = resolved
        if sig_id in seen_ids:
            continue
        seen_ids.add(sig_id)
        resolved_ids.append(sig_id)

    if len(resolved_ids) < 2:
        return AiAnswerResponse(
            answer="I could not resolve enough inscription IDs to compare similarities.",
            matched_inscriptions=0,
            metadata={"unresolved_candidates": unresolved, "resolved_count": len(resolved_ids)},
            error="Too few resolved signatures",
        )

    signatures = Signature.objects.in_bulk(resolved_ids)
    metas = list(
        MetaInformation.objects.select_related("signature", "materialType").filter(signature_id__in=resolved_ids).iterator()
    )
    meta_by_sig = {meta.signature_id: meta for meta in metas}
    ordered_pairs: list[tuple[str, MetaInformation]] = []
    for sig_id in resolved_ids:
        sig = signatures.get(sig_id)
        meta = meta_by_sig.get(sig_id)
        if sig and meta:
            ordered_pairs.append((sig.signature_text, meta))

    if len(ordered_pairs) < 2:
        return AiAnswerResponse(
            answer="I resolved signatures, but too few had metadata to compare.",
            matched_inscriptions=len(ordered_pairs),
            metadata={"resolved_signatures": [s.signature_text for s in signatures.values()], "unresolved_candidates": unresolved},
            error="Too few comparable inscriptions",
        )

    field_specs = [
        ("Dating", lambda m: m.dating),
        ("Rune type", lambda m: m.rune_type),
        ("Style", lambda m: m.style),
        ("Carver", lambda m: m.carver),
        ("Material type", lambda m: m.materialType.name if m.materialType else ""),
        ("Material", lambda m: m.material),
        ("Object info", lambda m: m.objectInfo),
        ("Found location", lambda m: m.found_location),
        ("Parish", lambda m: m.parish),
        ("District", lambda m: m.district),
        ("Municipality", lambda m: m.municipality),
        ("Current location", lambda m: m.current_location),
        ("Original site", lambda m: m.original_site),
    ]

    shared_exact, frequent_patterns = _compute_similarity_patterns(ordered_pairs, field_specs)

    signature_list = [sig for sig, _ in ordered_pairs]
    if shared_exact:
        shared_text = "; ".join(shared_exact[:8])
    elif frequent_patterns:
        shared_text = "No strict value shared by all. Strong patterns: " + "; ".join(frequent_patterns[:8])
    else:
        shared_text = "No strong shared metadata pattern was detected across the compared fields."

    answer = (
        f"I compared {len(signature_list)} inscriptions: {', '.join(signature_list)}. "
        f"{shared_text}"
    )
    if unresolved:
        answer += f" Could not resolve: {', '.join(unresolved)}."

    return AiAnswerResponse(
        answer=answer,
        matched_inscriptions=len(signature_list),
        metadata={
            "resolved_signatures": signature_list,
            "unresolved_candidates": unresolved,
            "shared_exact": shared_exact,
            "frequent_patterns": frequent_patterns,
        },
    )


def _answer_similarity_from_filters(user_text: str) -> AiAnswerResponse:
    qs, dating_prefix, country_codes = _build_meta_queryset_from_text(user_text)
    metas = list(qs.iterator())
    if len(metas) < 2:
        return AiAnswerResponse(
            answer="I found fewer than 2 matching inscriptions, so there is not enough data to compare similarities.",
            matched_inscriptions=len(metas),
            metadata={
                "country_codes": country_codes,
                "dating_prefix": dating_prefix,
            },
            error="Too few matches for comparison",
        )

    ordered_pairs = [(meta.signature.signature_text, meta) for meta in metas]
    field_specs = [
        ("Dating", lambda m: m.dating),
        ("Rune type", lambda m: m.rune_type),
        ("Style", lambda m: m.style),
        ("Carver", lambda m: m.carver),
        ("Material type", lambda m: m.materialType.name if m.materialType else ""),
        ("Material", lambda m: m.material),
        ("Object info", lambda m: m.objectInfo),
        ("Found location", lambda m: m.found_location),
        ("Parish", lambda m: m.parish),
        ("District", lambda m: m.district),
        ("Municipality", lambda m: m.municipality),
        ("Current location", lambda m: m.current_location),
        ("Original site", lambda m: m.original_site),
    ]
    shared_exact, frequent_patterns = _compute_similarity_patterns(ordered_pairs, field_specs)

    if shared_exact:
        shared_text = "; ".join(shared_exact[:10])
    elif frequent_patterns:
        shared_text = "No strict value shared by all. Strong patterns: " + "; ".join(frequent_patterns[:10])
    else:
        shared_text = "No strong shared metadata pattern was detected across compared fields."

    answer = f"I compared {len(ordered_pairs)} matching inscriptions. {shared_text}"
    return AiAnswerResponse(
        answer=answer,
        matched_inscriptions=len(ordered_pairs),
        metadata={
            "shared_exact": shared_exact,
            "frequent_patterns": frequent_patterns,
            "country_codes": country_codes,
            "dating_prefix": dating_prefix,
        },
    )


def _extract_requested_limit(user_text: str, default_value: int = 20, max_value: int = 200) -> int:
    text = user_text or ""
    m = re.search(r"\b(?:top|first|show|visa|de första|de forsta|max)\s+(\d{1,3})\b", text, flags=re.IGNORECASE)
    if not m:
        return default_value
    try:
        value = int(m.group(1))
        return max(1, min(max_value, value))
    except Exception:
        return default_value


def _looks_like_count_question(user_text: str) -> bool:
    text = _fold_text(user_text or "")
    return any(token in text for token in ("how many", "hur manga", "antal", "count"))


def _answer_count_from_filters(user_text: str) -> AiAnswerResponse:
    qs, dating_prefix, country_codes = _build_meta_queryset_from_text(user_text)
    count = qs.count()
    answer = f"I found {count} inscriptions matching your query."
    return AiAnswerResponse(
        answer=answer,
        matched_inscriptions=count,
        metadata={
            "count": count,
            "country_codes": country_codes,
            "dating_prefix": dating_prefix,
        },
    )


def _looks_like_list_question(user_text: str) -> bool:
    text = _fold_text(user_text or "")
    return any(token in text for token in ("which", "vilka", "list", "lista", "ta fram", "show all"))


def _answer_list_from_filters(user_text: str) -> AiAnswerResponse:
    qs, dating_prefix, country_codes = _build_meta_queryset_from_text(user_text)
    total = qs.count()
    limit = _extract_requested_limit(user_text, default_value=60, max_value=300)
    metas = list(qs.select_related("signature").order_by("signature__signature_text")[:limit])
    signatures = [meta.signature.signature_text for meta in metas]
    if total == 0:
        answer = "I found 0 inscriptions matching your query."
    elif total <= limit:
        answer = f"I found {total} inscriptions: {', '.join(signatures)}"
    else:
        answer = f"I found {total} inscriptions. Showing first {limit}: {', '.join(signatures)}"

    return AiAnswerResponse(
        answer=answer,
        matched_inscriptions=total,
        metadata={
            "signatures": signatures,
            "shown_count": len(signatures),
            "total_count": total,
            "country_codes": country_codes,
            "dating_prefix": dating_prefix,
        },
    )


def _extract_top_dimension(user_text: str) -> Optional[tuple[str, Any]]:
    text = _fold_text(user_text or "")
    if any(token in text for token in ("carver", "carvers", "ristare")):
        return ("Carver", lambda m: str(m.carver or "").strip())
    if any(token in text for token in ("material type", "materialtyp")):
        return ("Material type", lambda m: m.materialType.name if m.materialType else "")
    if any(token in text for token in ("material",)):
        return ("Material", lambda m: str(m.material or "").strip())
    if any(token in text for token in ("rune type", "runtyper", "runtyp")):
        return ("Rune type", lambda m: str(m.rune_type or "").strip())
    if any(token in text for token in ("style", "stil")):
        return ("Style", lambda m: str(m.style or "").strip())
    if any(token in text for token in ("parish", "socken")):
        return ("Parish", lambda m: str(m.parish or "").strip())
    if any(token in text for token in ("district", "harad", "härad")):
        return ("District", lambda m: str(m.district or "").strip())
    if any(token in text for token in ("municipality", "kommun")):
        return ("Municipality", lambda m: str(m.municipality or "").strip())
    if any(token in text for token in ("current location", "placering", "location")):
        return ("Current location", lambda m: str(m.current_location or "").strip())
    if any(token in text for token in ("dating", "period", "era", "age", "tid")):
        return ("Dating", lambda m: str(m.dating or "").strip())
    return None


def _looks_like_top_question(user_text: str) -> bool:
    text = _fold_text(user_text or "")
    return any(token in text for token in ("most common", "vanligaste", "top ", "flest", "common"))


def _answer_top_dimension_from_filters(user_text: str) -> AiAnswerResponse:
    dimension = _extract_top_dimension(user_text)
    if dimension is None:
        return AiAnswerResponse(
            answer="I could not identify what dimension to rank (for example carver, material, rune type, style).",
            matched_inscriptions=0,
            metadata={},
            error="Unknown top-dimension",
        )
    dim_label, getter = dimension
    qs, dating_prefix, country_codes = _build_meta_queryset_from_text(user_text)
    metas = list(qs.select_related("materialType").iterator())
    total = len(metas)
    if total == 0:
        return AiAnswerResponse(
            answer="I found 0 inscriptions matching your query.",
            matched_inscriptions=0,
            metadata={
                "dimension": dim_label,
                "rows": [],
                "country_codes": country_codes,
                "dating_prefix": dating_prefix,
            },
        )

    counts: Counter[str] = Counter()
    for meta in metas:
        value = str(getter(meta) or "").strip()
        if value:
            counts[value] += 1

    if not counts:
        return AiAnswerResponse(
            answer=f"I found {total} matching inscriptions, but no values for {dim_label}.",
            matched_inscriptions=total,
            metadata={
                "dimension": dim_label,
                "rows": [],
                "country_codes": country_codes,
                "dating_prefix": dating_prefix,
            },
        )

    limit = _extract_requested_limit(user_text, default_value=10, max_value=30)
    top_rows = counts.most_common(limit)
    rendered = "; ".join([f"{value} ({cnt})" for value, cnt in top_rows])
    answer = f"Top {len(top_rows)} {dim_label} values among {total} matching inscriptions: {rendered}"
    return AiAnswerResponse(
        answer=answer,
        matched_inscriptions=total,
        metadata={
            "dimension": dim_label,
            "rows": top_rows,
            "country_codes": country_codes,
            "dating_prefix": dating_prefix,
        },
    )


def _looks_like_most_productive_carver_question(user_text: str) -> bool:
    text = _fold_text(user_text or "")
    mentions_carver = any(token in text for token in ("ristare", "carver"))
    asks_most_productive = any(
        token in text for token in ("mest produktiv", "mest produktive", "most productive", "flest")
    )
    return mentions_carver and asks_most_productive


def _answer_most_productive_carver(user_text: str) -> AiAnswerResponse:
    qs, dating_prefix, country_codes = _build_meta_queryset_from_text(user_text)
    metas = list(qs.iterator())
    total = len(metas)
    if total == 0:
        return AiAnswerResponse(
            answer="Jag hittade 0 matchande inskrifter.",
            matched_inscriptions=0,
            metadata={
                "country_codes": country_codes,
                "dating_prefix": dating_prefix,
                "rows": [],
            },
        )

    counts: Counter[str] = Counter()
    for meta in metas:
        names = _extract_unique_carvers(meta.carver or "")
        # Count each carver at most once per inscription.
        for name in names:
            counts[name] += 1

    if not counts:
        return AiAnswerResponse(
            answer=f"Jag hittade {total} matchande inskrifter, men inga identifierade ristare i materialet.",
            matched_inscriptions=total,
            metadata={
                "country_codes": country_codes,
                "dating_prefix": dating_prefix,
                "rows": [],
            },
        )

    top_rows = counts.most_common(5)
    winner_name, winner_count = top_rows[0]
    answer = (
        f"Den mest produktive ristaren är {winner_name}, med {winner_count} inskrifter i urvalet. "
        f"(Urval: {total} matchande inskrifter.)"
    )
    return AiAnswerResponse(
        answer=answer,
        matched_inscriptions=total,
        metadata={
            "winner": {"name": winner_name, "count": winner_count},
            "rows": top_rows,
            "country_codes": country_codes,
            "dating_prefix": dating_prefix,
        },
    )


def _looks_like_period_frequency_question(user_text: str) -> bool:
    text = _fold_text(user_text or "")
    asks_period = any(token in text for token in ("which period", "vilken period", "period", "dating", "datering"))
    asks_compare = any(token in text for token in ("more", "most", "flest", "compare", "jämför", "jamfor", "or"))
    mentions_period_codes = bool(re.search(r"\bu\b|\bv\b|\bm\b", text))
    return asks_period and (asks_compare or mentions_period_codes)


STYLE_HELP_URL = "https://rundata-net.readthedocs.io/en/latest/db/data.html#figure-styles"


def _looks_like_style_explanation_question(user_text: str) -> bool:
    text = _fold_text(user_text or "")
    asks_definition = any(
        token in text
        for token in (
            "what is",
            "what does",
            "explain",
            "vad ar",
            "vad betyder",
            "forklara",
            "förklara",
        )
    )
    mentions_style_code = bool(re.search(r"\b(fp|kb|rak|sod|pr\s*[1-5])\b", text))
    return asks_definition and mentions_style_code


def _answer_style_explanation(user_text: str) -> AiAnswerResponse:
    text = _fold_text(user_text or "")
    requested_codes: list[str] = []
    for code in ("Fp", "Kb", "Rak", "Sod"):
        if re.search(rf"\b{re.escape(code.lower())}\b", text):
            requested_codes.append(code)
    for match in re.finditer(r"\bpr\s*([1-5])\b", text):
        requested_codes.append(f"Pr {match.group(1)}")

    if not requested_codes:
        requested_codes = ["Pr 1-5", "Fp", "Kb", "Rak", "Sod"]

    unique_codes = []
    seen = set()
    for code in requested_codes:
        if code.lower() not in seen:
            seen.add(code.lower())
            unique_codes.append(code)

    codes_text = ", ".join(unique_codes)
    verb = "belongs" if len(unique_codes) == 1 else "belong"
    answer = (
        f"{codes_text} {verb} to the Style filter. Style grouping information "
        "(Pr1-Pr5, Fp, KB, RAK) follows A.-S. Gräslund's chronological system "
        "for Viking Age runestones. The runestone material from the Mälar valley "
        "was dated by A.-S. Gräslund, and other runestones by A.-S. Gräslund "
        "and L. Lager in cooperation. See Help: Style: "
        f"{STYLE_HELP_URL}"
    )
    return AiAnswerResponse(
        answer=answer,
        matched_inscriptions=0,
        metadata={
            "style_codes": unique_codes,
            "help_url": STYLE_HELP_URL,
        },
    )


def _answer_period_frequency_from_filters(user_text: str) -> AiAnswerResponse:
    # For period comparison questions, do not force a single dating constraint from text.
    qs, _, country_codes = _build_meta_queryset_from_text(user_text, ignore_dating_constraint=True)
    metas = list(qs.iterator())
    total = len(metas)
    if total == 0:
        return AiAnswerResponse(
            answer="I found 0 matching inscriptions for this comparison.",
            matched_inscriptions=0,
            metadata={"period_counts": {}, "country_codes": country_codes},
        )

    requested_codes = _extract_requested_period_codes(user_text)
    counts: dict[str, int] = {code: 0 for code in requested_codes}
    for meta in metas:
        dating = str(meta.dating or "").strip().upper()
        if not dating:
            continue
        first = dating[0]
        if first in counts:
            counts[first] += 1

    winner_code = max(counts, key=lambda key: counts[key])
    winner_count = counts[winner_code]
    rendered = ", ".join([f"{code}: {counts[code]}" for code in requested_codes])
    answer = (
        f"For the selected inscriptions, the highest frequency is period {winner_code} "
        f"with {winner_count} inscriptions. Counts: {rendered}."
    )
    return AiAnswerResponse(
        answer=answer,
        matched_inscriptions=total,
        metadata={
            "period_counts": counts,
            "winner_period": winner_code,
            "winner_count": winner_count,
            "country_codes": country_codes,
            "requested_periods": requested_codes,
        },
    )


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


@api.post("/ai-answer", response=AiAnswerResponse, tags=["Rules"])
def ai_answer(request, data: TextRequest):
    """
    Answer DB-driven analytical questions. Initial response mode supports
    counting distinct carvers in user-constrained result sets.
    """
    if _looks_like_style_explanation_question(data.text):
        return _answer_style_explanation(data.text)

    if _looks_like_similarity_question(data.text):
        return _answer_signature_similarity(data.text)

    if _looks_like_similarity_over_filters_question(data.text):
        return _answer_similarity_from_filters(data.text)

    if _looks_like_period_frequency_question(data.text):
        return _answer_period_frequency_from_filters(data.text)

    if _looks_like_most_productive_carver_question(data.text):
        return _answer_most_productive_carver(data.text)

    if _looks_like_uninterpreted_question(data.text):
        return _answer_uninterpreted_inscriptions(data.text)

    if _looks_like_carver_count_question(data.text):
        return _answer_how_many_carvers(data.text)

    if _looks_like_top_question(data.text):
        return _answer_top_dimension_from_filters(data.text)

    if _looks_like_count_question(data.text):
        return _answer_count_from_filters(data.text)

    if _looks_like_list_question(data.text):
        return _answer_list_from_filters(data.text)

    return AiAnswerResponse(
        answer=(
            "Response mode is active, but this question type is not implemented yet. "
            "Try questions like: 'How many inscriptions ...', 'Which inscriptions ...', "
            "'Most common carvers in ...', or 'Compare them and find similarities'."
        ),
        matched_inscriptions=0,
        metadata={},
        error="Unsupported analytical question type",
    )


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
