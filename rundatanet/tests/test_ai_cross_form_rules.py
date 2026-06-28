import json

from django.test import TestCase

from rundatanet.runes.api import (
    CROSS_FORM_HELP_URL,
    _answer_cross_form_explanation,
    _build_rules_fallback_from_text,
    _cross_form_context_note,
    _postprocess_ai_rules,
)


def _field_values_from_tree(node, field):
    values = []
    if isinstance(node, dict) and isinstance(node.get("rules"), list):
        for child in node["rules"]:
            values.extend(_field_values_from_tree(child, field))
    elif isinstance(node, dict) and node.get("id") == field:
        values.append(node.get("value"))
    return values


def _or_groups_from_tree(node):
    groups = []
    if isinstance(node, dict) and isinstance(node.get("rules"), list):
        if node.get("condition") == "OR":
            groups.append(node)
        for child in node["rules"]:
            groups.extend(_or_groups_from_tree(child))
    return groups


class TestAiCrossFormRules(TestCase):
    databases = {"default", "runes_db"}

    def test_cross_form_code_uses_structured_cross_form_rule(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta inskrifter med korsform A1"))

        assert _field_values_from_tree(rules, "cross_form") == [{"form": "A1", "is_certain": "2"}]
        assert _field_values_from_tree(rules, "objectInfo") == []

    def test_uncertain_cross_form_uses_is_certain_no(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta inskrifter med osäker korsform E10"))

        assert _field_values_from_tree(rules, "cross_form") == [{"form": "E10", "is_certain": "0"}]

    def test_question_mark_cross_form_uses_is_certain_no(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta inskrifter med korsform A1?"))

        assert _field_values_from_tree(rules, "cross_form") == [{"form": "A1", "is_certain": "0"}]

    def test_certain_cross_form_uses_is_certain_yes(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta inskrifter med säker korsform B3"))

        assert _field_values_from_tree(rules, "cross_form") == [{"form": "B3", "is_certain": "1"}]

    def test_multiple_cross_forms_are_separate_and_rules(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta inskrifter med korsformerna A1 och B3"))

        assert _field_values_from_tree(rules, "cross_form") == [
            {"form": "A1", "is_certain": "2"},
            {"form": "B3", "is_certain": "2"},
        ]

    def test_runes_inside_cross_maps_to_group_g_non_zero_forms(self):
        rules = json.loads(_build_rules_fallback_from_text("Find inscriptions with crosses which contain runes inside a cross"))

        groups = _or_groups_from_tree(rules)
        assert groups
        assert _field_values_from_tree(groups[0], "cross_form") == [
            {"form": "G1", "is_certain": "2"},
            {"form": "G2", "is_certain": "2"},
            {"form": "G3", "is_certain": "2"},
            {"form": "G4", "is_certain": "2"},
            {"form": "G5", "is_certain": "2"},
            {"form": "G6", "is_certain": "2"},
        ]
        assert _field_values_from_tree(rules, "normalization_scandinavian_to_transliteration") == []

    def test_cross_without_runes_maps_to_group_g_zero(self):
        rules = json.loads(_build_rules_fallback_from_text("Find inscriptions with crosses without runes"))

        assert _field_values_from_tree(rules, "cross_form") == [{"form": "G0", "is_certain": "2"}]

    def test_ornamental_decoration_maps_to_group_e_non_zero_forms(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta inskrifter med kors med ornamental decoration"))

        groups = _or_groups_from_tree(rules)
        assert groups
        values = _field_values_from_tree(groups[0], "cross_form")
        assert values[0] == {"form": "E1", "is_certain": "2"}
        assert values[-1] == {"form": "E11", "is_certain": "2"}
        assert {"form": "E0", "is_certain": "2"} not in values

    def test_without_ornamental_decoration_maps_to_group_e_zero(self):
        rules = json.loads(_build_rules_fallback_from_text("Hitta inskrifter med kors utan dekoration"))

        assert _field_values_from_tree(rules, "cross_form") == [{"form": "E0", "is_certain": "2"}]
        assert _field_values_from_tree(rules, "objectInfo") == []

    def test_attached_to_runic_band_maps_to_group_c_non_zero_forms(self):
        rules = json.loads(_build_rules_fallback_from_text("Find inscriptions with crosses attached to the runic band"))

        groups = _or_groups_from_tree(rules)
        assert groups
        values = _field_values_from_tree(groups[0], "cross_form")
        assert values[0] == {"form": "C1", "is_certain": "2"}
        assert values[-1] == {"form": "C11", "is_certain": "2"}
        assert {"form": "C0", "is_certain": "2"} not in values

    def test_group_g_phrase_maps_to_group_g_non_zero_forms(self):
        rules = json.loads(_build_rules_fallback_from_text("Find inscriptions with Group G cross forms"))

        groups = _or_groups_from_tree(rules)
        assert groups
        assert _field_values_from_tree(groups[0], "cross_form")[0] == {"form": "G1", "is_certain": "2"}
        assert _field_values_from_tree(groups[0], "cross_form")[-1] == {"form": "G6", "is_certain": "2"}

    def test_postprocess_removes_object_kors_when_cross_form_is_requested(self):
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

        rules = json.loads(_postprocess_ai_rules("Hitta inskrifter med korsform A1", llm_rules))

        assert _field_values_from_tree(rules, "cross_form") == [{"form": "A1", "is_certain": "2"}]
        assert _field_values_from_tree(rules, "objectInfo") == []

    def test_postprocess_removes_noise_rules_for_descriptive_group_g_query(self):
        llm_rules = json.dumps(
            {
                "condition": "AND",
                "rules": [
                    {
                        "id": "normalization_scandinavian_to_transliteration",
                        "field": "normalisation_scandinavian",
                        "type": "string",
                        "operator": "contains",
                        "value": {
                            "normalization": "",
                            "transliteration": "inside",
                            "names_mode": "includeAll",
                        },
                    },
                    {
                        "id": "objectInfo",
                        "field": "objectInfo",
                        "type": "string",
                        "input": "text",
                        "operator": "contains",
                        "value": "kors",
                    },
                ],
                "not": False,
                "valid": True,
            }
        )

        rules = json.loads(
            _postprocess_ai_rules(
                "Find inscriptions with crosses which contain runes inside a cross",
                llm_rules,
            )
        )

        assert _field_values_from_tree(rules, "objectInfo") == []
        assert _field_values_from_tree(rules, "normalization_scandinavian_to_transliteration") == []
        values = _field_values_from_tree(rules, "cross_form")
        assert values[0] == {"form": "G1", "is_certain": "2"}
        assert values[-1] == {"form": "G6", "is_certain": "2"}

    def test_cross_form_explanation_mentions_lager_groups_and_documentation(self):
        response = _answer_cross_form_explanation("Vad betyder korsform A1?")

        assert "Linn Lager" in response.answer
        assert "Group A" in response.answer
        assert "centre" in response.answer
        assert CROSS_FORM_HELP_URL in response.answer
        assert response.metadata["cross_form_requests"] == [{"form": "A1", "is_certain": "2"}]

    def test_cross_form_context_note_for_reply_mode(self):
        note = _cross_form_context_note("Hur många inskrifter har korsform A1?")

        assert "A1" in note
        assert "A–G" in note
        assert CROSS_FORM_HELP_URL in note

    def test_cross_form_context_note_for_group_description(self):
        note = _cross_form_context_note("How many inscriptions have runes inside a cross?")

        assert "Group G" in note
        assert "G1–G6" in note
        assert CROSS_FORM_HELP_URL in note
