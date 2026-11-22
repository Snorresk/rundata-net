import importlib.resources
import logging
from typing import Optional

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

MODEL_READ_TIMEOUT_SECONDS = 20


def clean_llm_response(llm_response: str) -> str:
    if "<|fim_suffix|>" in llm_response:
        llm_response = llm_response.split("<|fim_suffix|>")[0]
    if "```json" in llm_response:
        llm_response = llm_response.split("```json", 1)[1]
    if "```" in llm_response:
        llm_response = llm_response.rsplit("```", 1)[0]

    return llm_response.strip()


def _get_system_message() -> dict[str, str]:
    """
    Get the system message for the model.
    """
    # Load the system message from a file
    system_prompt = (
        importlib.resources.files("rundatanet.runes")
        .joinpath("prompt.txt")
        .read_text(encoding="utf-8")
    )
    return {"role": "system", "content": system_prompt}


def inference(user_msg: str, api_token: Optional[str] = None) -> str:
    endpoint = settings.MODEL_ENDPOINT
    model_name = settings.MODEL_NAME
    api_token = api_token or settings.MODEL_KEY

    if not endpoint:
        raise ValueError("MODEL_ENDPOINT is not configured")
    if not model_name:
        raise ValueError("MODEL_NAME is not configured")
    if not api_token:
        raise ValueError("MODEL_KEY is not configured")

    client = OpenAI(
        base_url=f"{endpoint.rstrip('/')}/",
        api_key=api_token,
        timeout=MODEL_READ_TIMEOUT_SECONDS,
        max_retries=0,
    )
    system_prompt = _get_system_message()

    request_options = {
        "model": model_name,
        "messages": [system_prompt, {"role": "user", "content": user_msg}],
    }
    if settings.MODEL_REASONING_EFFORT:
        request_options["reasoning_effort"] = settings.MODEL_REASONING_EFFORT

    response = client.chat.completions.create(**request_options)
    choice = response.choices[0]
    if choice.finish_reason == "length":
        logger.warning("Model %s reached its completion length limit.", model_name)
        return ""

    response_text = choice.message.content or ""
    logger.debug("Raw LLM response: %s", response_text)

    return clean_llm_response(response_text)
