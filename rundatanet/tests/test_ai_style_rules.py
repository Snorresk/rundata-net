import json

from django.test import TestCase

from rundatanet.runes.api import (
    STYLE_HELP_URL,
    _answer_style_explanation,
    _build_rules_fallback_from_text,
    _postprocess_ai_rules,
    _style_context_note,
)


def _style_values_from_tree(node):
    values = []
    if isinstance(node, dict) and isinstance(node.get("rules"), list):
        for child in node["rules"]:
            values.extend(_style_values_from_tree(child))
    elif isinstance(node, dict) and node.get("id") == "style":
        values.append((node.get("operator"), node.get("value")))
    return values


def _field_values_from_tree(node, field):
    values = []
    if isinstance(node, dict) and isinstance(node.get("rules"), list):
        for child in node["rules"]:
            values.extend(_field_values_from_tree(child, field))
    elif isinstance(node, dict) and node.get("id") == field:
        values.append((node.get("operator"), node.get("value")))
    return values


class TestAiStyleRules(TestCase):
    databases = {"default", "runes_db"}

    def test_urnes_style_becomes_pr3_to_pr5_or_group(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta alla inskrifter i Urnesstil"))

        assert rules["condition"] == "AND"
        style_groups = [
            rule for rule in rules["rules"]
            if isinstance(rule, dict) and rule.get("condition") == "OR"
        ]
        assert style_groups, "Urnes style should be represented as an OR style group"
        assert set(_style_values_from_tree(style_groups[0])) == {
            ("contains", "Pr 3"),
            ("contains", "Pr 4"),
            ("contains", "Pr 5"),
        }
        assert _field_values_from_tree(rules, "full_address") == []

    def test_certain_urnes_style_excludes_question_mark(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta alla säkra inskrifter i Urnesstil utan frågetecken"))

        assert ("not_contains", "?") in _style_values_from_tree(rules)
        assert {value for _operator, value in _style_values_from_tree(rules)}.issuperset({"Pr 3", "Pr 4", "Pr 5"})
        assert _field_values_from_tree(rules, "full_address") == []

    def test_uncertain_ringerike_style_requires_question_mark(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta osäkra inskrifter i Ringerikestil"))

        assert ("contains", "?") in _style_values_from_tree(rules)
        assert {value for _operator, value in _style_values_from_tree(rules)}.issuperset({"Pr 1", "Pr 2"})
        assert _field_values_from_tree(rules, "full_address") == []

    def test_style_phrase_stilen_rak_does_not_become_location(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta alla inskrifter i stilen Rak"))

        assert _style_values_from_tree(rules) == [("contains", "Rak")]
        assert _field_values_from_tree(rules, "full_address") == []

    def test_style_phrase_stilen_pr1_does_not_become_location(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta alla inskrifter i stilen Pr1"))

        assert _style_values_from_tree(rules) == [("contains", "Pr 1")]
        assert _field_values_from_tree(rules, "full_address") == []

    def test_postprocess_replaces_literal_urnes_style_rule(self):
        llm_rules = json.dumps(
            {
                "condition": "AND",
                "rules": [
                    {
                        "id": "style",
                        "field": "style",
                        "type": "string",
                        "input": "text",
                        "operator": "contains",
                        "value": "Urnesstil",
                    }
                ],
                "not": False,
                "valid": True,
            }
        )

        rules = json.loads(_postprocess_ai_rules("Hitta alla inskrifter i Urnesstil", llm_rules))

        style_values = _style_values_from_tree(rules)
        assert ("contains", "Urnesstil") not in style_values
        assert set(style_values) == {
            ("contains", "Pr 3"),
            ("contains", "Pr 4"),
            ("contains", "Pr 5"),
        }

    def test_postprocess_removes_style_phrase_from_location_rules(self):
        llm_rules = json.dumps(
            {
                "condition": "AND",
                "rules": [
                    {
                        "id": "style",
                        "field": "style",
                        "type": "string",
                        "input": "text",
                        "operator": "contains",
                        "value": "Rak",
                    },
                    {
                        "id": "full_address",
                        "field": "full_address",
                        "type": "string",
                        "input": "text",
                        "operator": "contains",
                        "value": "stilen Rak",
                    },
                ],
                "not": False,
                "valid": True,
            }
        )

        rules = json.loads(_postprocess_ai_rules("Hitta alla inskrifter i stilen Rak", llm_rules))

        assert _style_values_from_tree(rules) == [("contains", "Rak")]
        assert _field_values_from_tree(rules, "full_address") == []

    def test_postprocess_removes_truncated_pr_style_phrase_from_location_rules(self):
        llm_rules = json.dumps(
            {
                "condition": "AND",
                "rules": [
                    {
                        "id": "style",
                        "field": "style",
                        "type": "string",
                        "input": "text",
                        "operator": "contains",
                        "value": "Pr 1",
                    },
                    {
                        "id": "full_address",
                        "field": "full_address",
                        "type": "string",
                        "input": "text",
                        "operator": "contains",
                        "value": "stilen Pr",
                    },
                ],
                "not": False,
                "valid": True,
            }
        )

        rules = json.loads(_postprocess_ai_rules("Hitta alla inskrifter i stilen Pr1", llm_rules))

        assert _style_values_from_tree(rules) == [("contains", "Pr 1")]
        assert _field_values_from_tree(rules, "full_address") == []

    def test_style_explanation_mentions_codes_and_documentation(self):
        response = _answer_style_explanation("Vad betyder Urnesstil?")

        assert "Pr3–Pr5" in response.answer or "Pr 3" in response.answer
        assert "Urnes" in response.answer
        assert STYLE_HELP_URL in response.answer
        assert response.metadata["help_url"] == STYLE_HELP_URL

    def test_style_context_note_for_reply_mode(self):
        note = _style_context_note("How many inscriptions are in Ringerike style?")

        assert "Pr 1" in note
        assert "Pr 2" in note
        assert "Ringerike" in note
        assert STYLE_HELP_URL in note
