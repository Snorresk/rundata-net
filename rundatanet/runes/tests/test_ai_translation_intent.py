import json
from unittest.mock import patch

from django.test import SimpleTestCase

from rundatanet.runes.api import (
    _build_rules_fallback_from_text,
    _extract_aligned_word_spelling,
    _extract_carver_constraints,
    _extract_carver_status,
    _extract_english_translation_terms,
    _extract_excluded_initial_rune,
    _extract_location_terms,
    _extract_long_vowel,
    _extract_material_constraints,
    _extract_name_element,
    _extract_phrase_query,
    _extract_required_initial_runes,
    _extract_rune_type_constraints,
    _extract_sound_term,
    _extract_standalone_transliteration_rune,
    _has_coordinate_rune_intent,
    _excludes_palatal_r,
    _extract_rune_spelling,
    _extract_swedish_word_terms,
    _has_bind_rune_intent,
    _is_simple_deterministic_query,
    _postprocess_ai_rules,
)


class EnglishTranslationIntentTests(SimpleTestCase):
    prompt = "Find all inscriptions with the word stone"

    def test_extracts_word_as_english_translation_term(self):
        self.assertEqual(_extract_english_translation_terms(self.prompt), ["stone"])

    def test_word_stone_is_not_treated_as_material(self):
        self.assertEqual(_extract_material_constraints(self.prompt), [])

    def test_other_english_material_words_are_also_treated_as_text(self):
        for word in ("bone", "wood", "metal", "plaster"):
            with self.subTest(word=word):
                prompt = f"Find inscriptions with the word {word}"
                self.assertEqual(_extract_material_constraints(prompt), [])

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_fallback_targets_english_translation(self, _styles, _objects):
        result = json.loads(_build_rules_fallback_from_text(self.prompt))

        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "english_translation")
        self.assertEqual(result["rules"][0]["value"], "stone")

    @patch("rundatanet.runes.api._language_containing_word", return_value="old_scandinavian")
    def test_english_word_query_can_target_old_scandinavian_normalisation(self, _language):
        prompt = "Find inscriptions with the word þiagn"

        self.assertEqual(_extract_english_translation_terms(prompt), [])
        self.assertEqual(_extract_swedish_word_terms(prompt), ["þiagn"])

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._language_containing_word", return_value="old_scandinavian")
    def test_fallback_targets_old_scandinavian_for_english_word_query(
        self, _language, _styles, _objects
    ):
        prompt = "Find inscriptions with the word þiagn"

        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "normalization_scandinavian_to_transliteration")
        self.assertEqual(result["rules"][0]["value"]["normalization"], "þiagn")

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_postprocessor_replaces_mistaken_material_rule(self, _styles, _objects):
        model_output = json.dumps(
            {
                "condition": "AND",
                "rules": [
                    {
                        "id": "material_type",
                        "field": "material_type",
                        "operator": "contains",
                        "value": "stone",
                    }
                ],
            }
        )

        result = json.loads(_postprocess_ai_rules(self.prompt, model_output))

        self.assertEqual([rule["id"] for rule in result["rules"]], ["english_translation"])
        self.assertEqual(result["rules"][0]["value"], "stone")

    def test_explicit_material_intent_is_preserved(self):
        constraints = _extract_material_constraints("Find inscriptions carved on stone")

        self.assertEqual(constraints[0]["id"], "material_type")
        self.assertEqual(constraints[0]["value"], "stone")

    def test_word_and_different_explicit_material_are_kept_separate(self):
        constraints = _extract_material_constraints(
            "Find inscriptions with the word stone made of wood"
        )

        self.assertEqual(constraints, [{"id": "material_type", "field": "material_type", "value": "wood"}])

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_same_word_can_be_material_and_english_translation(self, _styles, _objects):
        prompt = "Find all inscription on stone with the word stone"

        result = json.loads(_build_rules_fallback_from_text(prompt))

        self.assertEqual(
            [(rule["id"], rule["value"]) for rule in result["rules"]],
            [("english_translation", "stone"), ("material_type", "stone")],
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_translation_word_combines_with_period_and_country(self, _styles, _objects):
        prompt = "Find Viking Age inscriptions from Norway with the word stone"

        result = json.loads(_build_rules_fallback_from_text(prompt))

        self.assertEqual(
            [(rule["id"], rule["value"]) for rule in result["rules"]],
            [
                ("dating", "V"),
                ("inscription_country", ["N "]),
                ("english_translation", "stone"),
            ],
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_word_runes_with_denmark_uses_fast_deterministic_path(self, _styles, _objects):
        prompt = "Find all inscription from Denmark with the word runes"

        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(
            [(rule["id"], rule["value"]) for rule in result["rules"]],
            [
                ("inscription_country", ["DR "]),
                ("english_translation", "runes"),
            ],
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._language_containing_word", return_value="old_west_norse")
    def test_swedish_word_targets_old_west_norse_not_location(self, _language, _styles, _objects):
        prompt = "Sök efter ordet ”eptir” i samtliga runinskrifter"

        self.assertEqual(_extract_swedish_word_terms(prompt), ["eptir"])
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "normalization_norse_to_transliteration")
        self.assertEqual(
            result["rules"][0]["value"],
            {"normalization": "eptir", "transliteration": "", "names_mode": "includeAll"},
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._language_containing_word", return_value="old_scandinavian")
    def test_swedish_word_falls_back_to_old_scandinavian(self, _language, _styles, _objects):
        prompt = "Sök efter ordet fiktivtord i samtliga runinskrifter"

        result = json.loads(_build_rules_fallback_from_text(prompt))

        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "normalization_scandinavian_to_transliteration")
        self.assertEqual(result["rules"][0]["value"]["normalization"], "fiktivtord")

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._language_containing_word", return_value="english_translation")
    def test_swedish_query_with_english_word_targets_english_translation(
        self, _language, _styles, _objects
    ):
        prompt = "Sök efter ordet runes i samtliga runinskrifter"

        result = json.loads(_build_rules_fallback_from_text(prompt))

        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "english_translation")
        self.assertEqual(result["rules"][0]["value"], "runes")

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._language_containing_word", return_value="swedish_translation")
    def test_swedish_word_can_target_swedish_translation(self, _language, _styles, _objects):
        prompt = "Sök efter ordet minnesmärke i samtliga runinskrifter"

        result = json.loads(_build_rules_fallback_from_text(prompt))

        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "swedish_translation")
        self.assertEqual(result["rules"][0]["value"], "minnesmärke")

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._language_containing_word", return_value="old_west_norse")
    def test_rune_spelling_pairs_normalization_and_transliteration(
        self, _language, _styles, _objects
    ):
        prompt = "Sök efter ordet ok, och, i stavningen ak"

        self.assertEqual(_extract_rune_spelling(prompt), "ak")
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "normalization_norse_to_transliteration")
        self.assertEqual(
            result["rules"][0]["value"],
            {"normalization": "ok", "transliteration": "ak", "names_mode": "includeAll"},
        )

    def test_rune_spelling_phrase_variants(self):
        prompts = (
            "Find the word ok, spelling in runes: ak",
            "Sök efter ordet ok och hur det ska skrivas med runor: ak",
            "Sök efter ordet ok, skrivet med runor som ak",
        )

        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertEqual(_extract_rune_spelling(prompt), "ak")

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._language_containing_word", return_value="old_west_norse")
    def test_english_word_written_with_runes_pairs_normalization_and_transliteration(
        self, _language, _styles, _objects
    ):
        prompt = "Find all inscriptions in Sweden where the word stæin is written with runes stan"

        self.assertEqual(_extract_aligned_word_spelling(prompt), ("stæin", "stan"))
        self.assertEqual(_extract_rune_spelling(prompt), "stan")
        self.assertEqual(_extract_english_translation_terms(prompt), [])
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(result["condition"], "AND")
        self.assertEqual(len(result["rules"]), 2)
        country_rule, word_rule = result["rules"]
        self.assertEqual(country_rule["id"], "inscription_country")
        self.assertEqual(country_rule["value"], ["all_sweden"])
        self.assertEqual(word_rule["id"], "normalization_norse_to_transliteration")
        self.assertEqual(
            word_rule["value"],
            {"normalization": "stæin", "transliteration": "stan", "names_mode": "includeAll"},
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._normalization_contains_word", return_value=True)
    def test_english_word_written_in_runes_uses_transliteration_not_location(
        self, _contains, _styles, _objects
    ):
        prompt = "Find inscriptions with the word þegn written in runes þikn."

        self.assertEqual(_extract_aligned_word_spelling(prompt), ("þegn", "þikn"))
        self.assertEqual(_extract_rune_spelling(prompt), "þikn")
        self.assertEqual(_extract_location_terms(prompt), [])

        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "normalization_scandinavian_to_transliteration")
        self.assertEqual(
            result["rules"][0]["value"],
            {"normalization": "þegn", "transliteration": "þikn", "names_mode": "includeAll"},
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._language_containing_word", return_value="old_west_norse")
    def test_swedish_word_written_with_single_rune_pairs_normalization_and_transliteration(
        self, _language, _styles, _objects
    ):
        prompt = "Hitta inskrifter med ordet reisti i Södermanland som skrivs med þ runa"

        self.assertEqual(_extract_aligned_word_spelling(prompt), ("reisti", "þ"))
        self.assertEqual(_extract_rune_spelling(prompt), "þ")
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(result["condition"], "AND")
        self.assertEqual(len(result["rules"]), 2)
        country_rule, word_rule = result["rules"]
        self.assertEqual(country_rule["id"], "inscription_country")
        self.assertEqual(country_rule["value"], ["Sö "])
        self.assertEqual(word_rule["id"], "normalization_norse_to_transliteration")
        self.assertEqual(
            word_rule["value"],
            {"normalization": "reisti", "transliteration": "þ", "names_mode": "includeAll"},
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._language_containing_word", return_value="old_west_norse")
    def test_postprocess_adds_missing_transliteration_to_combined_word_rune_query(
        self, _language, _styles, _objects
    ):
        prompt = "Hitta inskrifter med ordet reisti i Södermanland som skrivs med þ runa"
        llm_rules = json.dumps(
            {
                "condition": "AND",
                "rules": [
                    {
                        "id": "inscription_country",
                        "field": "signature_text",
                        "type": "string",
                        "input": "select",
                        "operator": "in",
                        "value": ["Sö "],
                        "data": {"multiField": True},
                    },
                    {
                        "id": "normalization_norse_to_transliteration",
                        "field": "normalization_norse",
                        "type": "string",
                        "operator": "contains",
                        "value": {
                            "normalization": "reisti",
                            "transliteration": "",
                            "names_mode": "includeAll",
                        },
                        "data": {"multiField": True},
                        "ignoreCase": True,
                        "includeSpecialSymbols": False,
                    },
                ],
                "not": False,
                "valid": True,
            }
        )

        result = json.loads(_postprocess_ai_rules(prompt, llm_rules))

        self.assertEqual(result["condition"], "AND")
        self.assertEqual(len(result["rules"]), 2)
        country_rule, word_rule = result["rules"]
        self.assertEqual(country_rule["id"], "inscription_country")
        self.assertEqual(country_rule["value"], ["Sö "])
        self.assertEqual(word_rule["id"], "normalization_norse_to_transliteration")
        self.assertEqual(
            word_rule["value"],
            {"normalization": "reisti", "transliteration": "þ", "names_mode": "includeAll"},
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._resolve_old_west_name_element", return_value="bjôrn")
    def test_name_element_is_resolved_and_paired_with_rune_spelling(
        self, _resolved_element, _styles, _objects
    ):
        prompt = "Sök efter samtliga fall där namnleden björn uppträder med skrivningen iau"

        self.assertEqual(_extract_name_element(prompt), "björn")
        self.assertEqual(_extract_rune_spelling(prompt), "iau")
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "normalization_norse_to_transliteration")
        self.assertEqual(
            result["rules"][0]["value"],
            {"normalization": "bjôrn", "transliteration": "iau", "names_mode": "namesOnly"},
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_postprocessor_disables_symbols_for_language_rules_by_default(self, _styles, _objects):
        model_output = json.dumps(
            {
                "condition": "AND",
                "rules": [
                    {
                        "id": "normalization_norse_to_transliteration",
                        "field": "normalization_norse",
                        "operator": "contains",
                        "value": {
                            "normalization": "eptir",
                            "transliteration": "",
                            "names_mode": "includeAll",
                        },
                        "includeSpecialSymbols": True,
                    }
                ],
            }
        )

        result = json.loads(_postprocess_ai_rules("Find normalized eptir", model_output))

        self.assertFalse(result["rules"][0]["includeSpecialSymbols"])

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_postprocessor_preserves_symbols_when_explicitly_requested(self, _styles, _objects):
        model_output = json.dumps(
            {
                "condition": "AND",
                "rules": [
                    {
                        "id": "normalization_norse_to_transliteration",
                        "field": "normalization_norse",
                        "operator": "contains",
                        "value": {
                            "normalization": "",
                            "transliteration": "^",
                            "names_mode": "includeAll",
                        },
                        "includeSpecialSymbols": True,
                    }
                ],
            }
        )

        result = json.loads(_postprocess_ai_rules("Find bind-runes using ^", model_output))

        self.assertTrue(result["rules"][0]["includeSpecialSymbols"])

    @patch("rundatanet.runes.api._get_object_info_values", return_value=(("sten", "sten"),))
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._resolve_old_west_name_element", return_value="stein")
    def test_name_element_can_match_inside_personal_names(
        self, _resolved_element, _styles, _object_values
    ):
        prompt = "Sök efter samtliga fall där namnleden sten uppträder med skrivningen ai"

        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(
            result["rules"][0]["value"],
            {"normalization": "stein", "transliteration": "ai", "names_mode": "namesOnly"},
        )
        self.assertFalse(result["rules"][0]["includeSpecialSymbols"])

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch(
        "rundatanet.runes.api._resolve_swedish_word_normalizations",
        return_value=("hjó", "hiogg"),
    )
    def test_swedish_word_can_exclude_an_initial_transliteration_rune(
        self, _normalizations, _styles, _objects
    ):
        prompt = "Sök efter ordet ”högg” där detta är stavat utan inledande h-runa"

        self.assertEqual(_extract_excluded_initial_rune(prompt), "h")
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 2)
        positive_rule, negated_group = result["rules"]
        self.assertEqual(positive_rule["id"], "normalization_scandinavian_to_transliteration")
        self.assertEqual(positive_rule["operator"], "contains")
        self.assertEqual(
            positive_rule["value"],
            {"normalization": "hiogg", "transliteration": "", "names_mode": "includeAll"},
        )
        self.assertTrue(negated_group["not"])
        self.assertEqual(negated_group["condition"], "AND")
        negative_rule = negated_group["rules"][0]
        self.assertEqual(negative_rule["id"], "normalization_scandinavian_to_transliteration")
        self.assertEqual(negative_rule["operator"], "begins_with")
        self.assertEqual(
            negative_rule["value"],
            {"normalization": "hiogg", "transliteration": "h", "names_mode": "includeAll"},
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    @patch("rundatanet.runes.api._language_containing_phrase", return_value="old_west_norse")
    def test_misspelled_phrase_intent_selects_language_and_keeps_words_together(
        self, _language, _styles, _objects
    ):
        prompt = "Find all inscriptions with fraise þenna stein"

        self.assertEqual(_extract_phrase_query(prompt), "þenna stein")
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "normalization_norse_to_transliteration")
        self.assertEqual(
            result["rules"][0]["value"],
            {"normalization": "þenna stein", "transliteration": "", "names_mode": "includeAll"},
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_multiple_lexical_terms_become_independent_rules(self, _styles, _objects):
        prompt = (
            "Sök efter inskrifter med det fornvästnordiska ordet kuml "
            "som också innehåller verbet reisa"
        )

        self.assertEqual(_extract_swedish_word_terms(prompt), ["kuml", "reisa"])
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(result["condition"], "AND")
        self.assertEqual(len(result["rules"]), 2)
        self.assertEqual(
            [rule["id"] for rule in result["rules"]],
            [
                "normalization_norse_to_transliteration",
                "normalization_norse_to_transliteration",
            ],
        )
        self.assertEqual(
            [rule["value"]["normalization"] for rule in result["rules"]],
            ["kuml", "reisa"],
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_required_initial_runes_create_aligned_begins_with_rule(self, _styles, _objects):
        prompt = (
            "Sök efter inskrifter med det fornvästnordiska ordet eptir "
            "där detta inleds med runorna ai"
        )

        self.assertEqual(_extract_required_initial_runes(prompt), "ai")
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 1)
        rule = result["rules"][0]
        self.assertEqual(rule["id"], "normalization_norse_to_transliteration")
        self.assertEqual(rule["operator"], "begins_with")
        self.assertEqual(
            rule["value"],
            {"normalization": "eptir", "transliteration": "ai", "names_mode": "includeAll"},
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_palatal_r_exclusion_adds_case_sensitive_aligned_not_group(self, _styles, _objects):
        prompt = (
            "Sök efter inskrifter med det fornvästnordiska ordet eptir där detta "
            "inleds med runorna ai men där det inte är stavat med ʀ "
            "(runan för så kallat palatalt r)"
        )

        self.assertTrue(_excludes_palatal_r(prompt))
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 2)
        positive_rule, negated_group = result["rules"]
        self.assertEqual(positive_rule["operator"], "begins_with")
        self.assertEqual(
            positive_rule["value"],
            {"normalization": "eptir", "transliteration": "ai", "names_mode": "includeAll"},
        )
        self.assertTrue(negated_group["not"])
        negative_rule = negated_group["rules"][0]
        self.assertEqual(negative_rule["operator"], "ends_with")
        self.assertEqual(
            negative_rule["value"],
            {"normalization": "eptir", "transliteration": "R", "names_mode": "includeAll"},
        )
        self.assertFalse(negative_rule["ignoreCase"])

    def test_palatal_r_exclusion_wording_variants(self):
        negative_prompts = (
            "Sök ordet eptir utan palatalt R",
            "Sök ordet eptir utan R-runan",
            "Find eptir without the R-rune",
            "Find eptir not written with rune R",
        )
        for prompt in negative_prompts:
            with self.subTest(prompt=prompt):
                self.assertTrue(_excludes_palatal_r(prompt))

        self.assertFalse(_excludes_palatal_r("Sök efter former med palatalt R"))

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_bind_runes_create_root_or_group(self, _styles, _objects):
        prompt = "hitta alla inskrifter med bindrunor"

        self.assertTrue(_has_bind_rune_intent(prompt))
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(result["condition"], "OR")
        self.assertEqual(len(result["rules"]), 2)
        symbol_rule, rune_type_rule = result["rules"]
        self.assertEqual(symbol_rule["id"], "normalization_scandinavian_to_transliteration")
        self.assertEqual(
            symbol_rule["value"],
            {"normalization": "", "transliteration": "^", "names_mode": "includeAll"},
        )
        self.assertTrue(symbol_rule["includeSpecialSymbols"])
        self.assertEqual(rune_type_rule["id"], "rune_type")
        self.assertEqual(rune_type_rule["value"], "bind")
        self.assertFalse(rune_type_rule["includeSpecialSymbols"])

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_staveless_runes_target_rune_type(self, _styles, _objects):
        prompt = "Hitta inskrifter med stavlösa runor"

        self.assertEqual(
            _extract_rune_type_constraints(prompt),
            [{"id": "rune_type", "field": "rune_type", "value": "stavlösa"}],
        )
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(result["condition"], "AND")
        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "rune_type")
        self.assertEqual(result["rules"][0]["value"], "stavlösa")
        self.assertTrue(result["rules"][0]["ignoreCase"])
        self.assertFalse(result["rules"][0]["includeSpecialSymbols"])

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_coordinate_rune_terms_target_transliteration_symbol(self, _styles, _objects):
        prompts = (
            "Hitta inskrifter med kvistrunor",
            "Hitta inskrifter skrivna med koordinatrunor",
            "Hitta inskrifter som använder chifferrunor",
            "Hitta inskrifter med lönnrunor",
            "Find inscriptions written with coordinate runes",
            "Find inscriptions with cipher runes",
            "Find inscriptions with secret runes",
            "Find inscriptions with twig runes",
            "Find inscriptions with branch runes",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertTrue(_has_coordinate_rune_intent(prompt))
                self.assertEqual(_extract_rune_type_constraints(prompt), [])
                self.assertIsNone(_extract_standalone_transliteration_rune(prompt))

                fallback = _build_rules_fallback_from_text(prompt)
                result = json.loads(fallback)

                self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
                self.assertEqual(result["condition"], "AND")
                self.assertEqual(len(result["rules"]), 1)
                rule = result["rules"][0]
                self.assertEqual(rule["id"], "normalization_scandinavian_to_transliteration")
                self.assertEqual(
                    rule["value"],
                    {"normalization": "", "transliteration": "<", "names_mode": "includeAll"},
                )
                self.assertTrue(rule["includeSpecialSymbols"])

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_long_vowel_always_targets_old_west_norse(self, _styles, _objects):
        prompt = "Hitta alla inskrifter med lång vokal a"

        self.assertEqual(_extract_long_vowel(prompt), "á")
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 1)
        rule = result["rules"][0]
        self.assertEqual(rule["id"], "normalization_norse_to_transliteration")
        self.assertEqual(rule["operator"], "contains")
        self.assertEqual(
            rule["value"],
            {"normalization": "á", "transliteration": "", "names_mode": "includeAll"},
        )

    def test_all_supported_long_vowels_receive_acute_accent(self):
        expected = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú", "y": "ý"}
        for vowel, accented in expected.items():
            with self.subTest(vowel=vowel):
                self.assertEqual(_extract_long_vowel(f"long vowel {vowel}"), accented)

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_long_vowel_and_rune_spelling_use_one_aligned_rule(self, _styles, _objects):
        prompt = "Hitta alla inskrifter med lång vokal o som skrivs u med runor"

        self.assertEqual(_extract_long_vowel(prompt), "ó")
        self.assertEqual(_extract_rune_spelling(prompt), "u")
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 1)
        rule = result["rules"][0]
        self.assertEqual(rule["id"], "normalization_norse_to_transliteration")
        self.assertEqual(rule["operator"], "contains")
        self.assertEqual(
            rule["value"],
            {"normalization": "ó", "transliteration": "u", "names_mode": "includeAll"},
        )

    def test_rune_spelling_after_sound_wording_variants(self):
        prompts = (
            "ljudet skrivs u med runor",
            "ljudet stavas u med runor",
            "the sound is written as u in runes",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertEqual(_extract_rune_spelling(prompt), "u")

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_initial_sound_spelling_uses_begins_with(self, _styles, _objects):
        prompt = "Hitta alla inskrifter där ljudet þ initialt skrivs med runan t"

        self.assertEqual(_extract_sound_term(prompt), "þ")
        self.assertEqual(_extract_required_initial_runes(prompt), "t")
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(len(result["rules"]), 1)
        rule = result["rules"][0]
        self.assertEqual(rule["id"], "normalization_norse_to_transliteration")
        self.assertEqual(rule["operator"], "begins_with")
        self.assertEqual(
            rule["value"],
            {"normalization": "þ", "transliteration": "t", "names_mode": "includeAll"},
        )


class CarverIntentTests(SimpleTestCase):
    def test_attributed_carver_adds_name_and_a_marker(self):
        prompt = "Find inscriptions attributed to the carver Öpir"

        self.assertEqual(_extract_carver_status(prompt), "A")
        self.assertEqual(
            _extract_carver_constraints(prompt),
            [
                {"id": "carver", "field": "carver", "value": "Öpir"},
                {"id": "carver", "field": "carver", "value": "(A)"},
            ],
        )

    def test_signed_carver_adds_name_and_s_marker(self):
        prompt = "Hitta inskrifter signerade av Åsmund"

        self.assertEqual(_extract_carver_status(prompt), "S")
        self.assertEqual(
            _extract_carver_constraints(prompt),
            [
                {"id": "carver", "field": "carver", "value": "Åsmund"},
                {"id": "carver", "field": "carver", "value": "(S)"},
            ],
        )

    def test_ristarsignatur_without_name_searches_signed_marker(self):
        prompt = "Hitta alla inskrifter med ristarsignatur"

        self.assertEqual(
            _extract_carver_constraints(prompt),
            [{"id": "carver", "field": "carver", "value": "(S)"}],
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_fallback_uses_separate_carver_marker_rule(self, _styles, _objects):
        prompt = "Find inscriptions attributed to the carver Öpir"

        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(
            [(rule["id"], rule["value"]) for rule in result["rules"]],
            [("carver", "Öpir"), ("carver", "(A)")],
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_postprocessor_splits_model_carver_value_with_marker(self, _styles, _objects):
        prompt = "Find inscriptions attributed to the carver Öpir"
        model_output = json.dumps(
            {
                "condition": "AND",
                "rules": [
                    {
                        "id": "carver",
                        "field": "carver",
                        "operator": "contains",
                        "value": "Öpir (A)",
                    }
                ],
            }
        )

        result = json.loads(_postprocess_ai_rules(prompt, model_output))

        self.assertEqual(len(result["rules"]), 1)
        split_group = result["rules"][0]
        self.assertEqual(split_group["condition"], "AND")
        self.assertEqual(
            [(rule["id"], rule["value"]) for rule in split_group["rules"]],
            [("carver", "Öpir"), ("carver", "(A)")],
        )

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_signed_carver_with_used_rune_adds_marker_and_transliteration(
        self, _styles, _objects
    ):
        prompt = "Hitta alla inskrifter signerade av ristare som använder runan o"

        self.assertEqual(_extract_carver_status(prompt), "S")
        self.assertEqual(_extract_standalone_transliteration_rune(prompt), "o")
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(result["condition"], "AND")
        self.assertEqual(len(result["rules"]), 2)
        transliteration_rule, carver_rule = result["rules"]
        self.assertEqual(transliteration_rule["id"], "normalization_scandinavian_to_transliteration")
        self.assertEqual(
            transliteration_rule["value"],
            {"normalization": "", "transliteration": "o", "names_mode": "includeAll"},
        )
        self.assertEqual(carver_rule["id"], "carver")
        self.assertEqual(carver_rule["value"], "(S)")

    @patch("rundatanet.runes.api._extract_object_info_constraints", return_value=[])
    @patch("rundatanet.runes.api._extract_style_constraints", return_value=[])
    def test_rune_value_with_denmark_targets_transliteration_and_country(
        self, _styles, _objects
    ):
        prompt = "Hitta alla runor R i Danmark"

        self.assertEqual(_extract_standalone_transliteration_rune(prompt), "R")
        fallback = _build_rules_fallback_from_text(prompt)
        result = json.loads(fallback)

        self.assertTrue(_is_simple_deterministic_query(prompt, fallback))
        self.assertEqual(result["condition"], "AND")
        self.assertEqual(len(result["rules"]), 2)
        country_rule, transliteration_rule = result["rules"]
        self.assertEqual(country_rule["id"], "inscription_country")
        self.assertEqual(country_rule["value"], ["DR "])
        self.assertEqual(transliteration_rule["id"], "normalization_scandinavian_to_transliteration")
        self.assertEqual(
            transliteration_rule["value"],
            {"normalization": "", "transliteration": "R", "names_mode": "includeAll"},
        )
