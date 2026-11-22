from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from rundatanet.runes.inference import clean_llm_response, inference


class InferenceTests(SimpleTestCase):
    @override_settings(
        MODEL_ENDPOINT="https://example.services.ai.azure.com/openai/v1",
        MODEL_NAME="gpt-6-luna",
        MODEL_KEY="test-key",
        MODEL_REASONING_EFFORT="",
    )
    @patch("rundatanet.runes.inference.OpenAI")
    def test_uses_openai_chat_completions(self, openai_mock):
        openai_mock.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content='```json\n{"rules": []}\n```'),
                )
            ]
        )

        result = inference("Find all inscriptions")

        self.assertEqual(result, '{"rules": []}')
        openai_mock.assert_called_once_with(
            base_url="https://example.services.ai.azure.com/openai/v1/",
            api_key="test-key",
            timeout=20,
            max_retries=0,
        )
        request = openai_mock.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], "gpt-6-luna")
        self.assertNotIn("max_completion_tokens", request)
        self.assertEqual(request["messages"][0]["role"], "system")
        self.assertEqual(
            request["messages"][1],
            {"role": "user", "content": "Find all inscriptions"},
        )
        self.assertNotIn("temperature", request)
        self.assertNotIn("top_p", request)
        self.assertNotIn("reasoning_effort", request)

    @override_settings(
        MODEL_ENDPOINT="https://example.services.ai.azure.com/openai/v1/",
        MODEL_NAME="gpt-6-luna",
        MODEL_KEY="configured-key",
        MODEL_REASONING_EFFORT="minimal",
    )
    @patch("rundatanet.runes.inference.OpenAI")
    def test_supports_key_override_and_optional_reasoning_effort(self, openai_mock):
        openai_mock.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="{}"))
            ]
        )

        inference("query", api_token="request-key")

        self.assertEqual(openai_mock.call_args.kwargs["api_key"], "request-key")
        request = openai_mock.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(request["reasoning_effort"], "minimal")

    @override_settings(
        MODEL_ENDPOINT="https://example.services.ai.azure.com/openai/v1",
        MODEL_NAME="gpt-6-luna",
        MODEL_KEY="test-key",
    )
    @patch("rundatanet.runes.inference.OpenAI")
    def test_discards_truncated_completion(self, openai_mock):
        openai_mock.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="length",
                    message=SimpleNamespace(content='{"rules": ['),
                )
            ]
        )

        self.assertEqual(inference("query"), "")

    @override_settings(
        MODEL_ENDPOINT="",
        MODEL_NAME="gpt-6-luna",
        MODEL_KEY="test-key",
    )
    def test_requires_endpoint(self):
        with self.assertRaisesMessage(ValueError, "MODEL_ENDPOINT is not configured"):
            inference("query")

    def test_clean_llm_response_handles_empty_content(self):
        self.assertEqual(clean_llm_response(""), "")
