import json

from django.test import TestCase

from rundatanet.runes.api import (
    _build_rules_fallback_from_text,
    _postprocess_ai_rules,
)


def _field_values_from_tree(node, field):
    values = []
    if isinstance(node, dict) and isinstance(node.get("rules"), list):
        for child in node["rules"]:
            values.extend(_field_values_from_tree(child, field))
    elif isinstance(node, dict) and node.get("id") == field:
        values.append((node.get("operator"), node.get("value")))
    return values


class TestAiCrossCountRules(TestCase):
    databases = {"default", "runes_db"}

    def test_swedish_number_of_crosses_uses_num_crosses(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta alla inskrifter med fyra kors"))

        assert _field_values_from_tree(rules, "num_crosses") == [("equal", 4)]
        assert _field_values_from_tree(rules, "objectInfo") == []

    def test_digit_number_of_crosses_uses_num_crosses(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta alla inskrifter med 4 kors"))

        assert _field_values_from_tree(rules, "num_crosses") == [("equal", 4)]
        assert _field_values_from_tree(rules, "objectInfo") == []

    def test_english_number_of_crosses_uses_num_crosses(self):
        rules = json.loads(_build_rules_fallback_from_text("Find all inscriptions with four crosses"))

        assert _field_values_from_tree(rules, "num_crosses") == [("equal", 4)]
        assert _field_values_from_tree(rules, "objectInfo") == []

    def test_minimum_number_of_crosses_uses_greater_or_equal(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta alla inskrifter med minst fyra kors"))

        assert _field_values_from_tree(rules, "num_crosses") == [("greater_or_equal", 4)]
        assert _field_values_from_tree(rules, "objectInfo") == []

    def test_postprocess_removes_object_kors_when_cross_count_is_requested(self):
        llm_rules = json.dumps(
            {
                "condition": "AND",
                "rules": [
                    {
                        "id": "objectInfo",
                        "field": "objectInfo",
                        "type": "string",
                        "input": "text",
                        "operator": "contains",
                        "value": "kors",
                    }
                ],
                "not": False,
                "valid": True,
            }
        )

        rules = json.loads(_postprocess_ai_rules("Hitta alla inskrifter med fyra kors", llm_rules))

        assert _field_values_from_tree(rules, "num_crosses") == [("equal", 4)]
        assert _field_values_from_tree(rules, "objectInfo") == []
