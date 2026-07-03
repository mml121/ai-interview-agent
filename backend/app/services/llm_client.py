import json
import re
from typing import Any

import httpx

from app.core.config import get_settings


class LLMClientError(RuntimeError):
    pass


def extract_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise LLMClientError("LLM response did not contain a JSON object")

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMClientError("LLM response JSON could not be parsed") from exc


def call_claude(messages: list[dict[str, str]]) -> str:
    settings = get_settings()

    if not settings.claude_enabled:
        raise LLMClientError("Claude endpoint is not configured")

    payload = {
        "model": settings.claude_model,
        "messages": messages,
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.claude_api_key or "",
    }

    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(
                settings.claude_api_url or "",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMClientError("Claude endpoint request failed") from exc

    data = response.json()
    content = data.get("content", [])

    if not content or not isinstance(content, list):
        raise LLMClientError("Claude response did not include content")

    first_part = content[0]

    if not isinstance(first_part, dict) or "text" not in first_part:
        raise LLMClientError("Claude response text was missing")

    return str(first_part["text"])


def call_openai(messages: list[dict[str, str]]) -> str:
    settings = get_settings()

    if not settings.openai_api_key:
        raise LLMClientError("OpenAI endpoint is not configured")

    payload = {
        "model": settings.openai_model,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(
                settings.openai_api_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMClientError("OpenAI endpoint request failed") from exc

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise LLMClientError("OpenAI response did not include choices")

    message = choices[0].get("message", {})
    content = message.get("content")
    if not content:
        raise LLMClientError("OpenAI response content was missing")

    return str(content)


def call_azure_openai(messages: list[dict[str, str]]) -> str:
    settings = get_settings()

    if not (
        settings.azure_openai_api_url
        and settings.azure_openai_api_key
        and settings.azure_openai_deployment
    ):
        raise LLMClientError("Azure OpenAI endpoint is not configured")

    base_url = settings.azure_openai_api_url.rstrip("/")
    endpoint = (
        f"{base_url}/openai/deployments/{settings.azure_openai_deployment}"
        f"/chat/completions?api-version={settings.azure_openai_api_version}"
    )
    payload = {
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "api-key": settings.azure_openai_api_key,
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMClientError("Azure OpenAI endpoint request failed") from exc

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise LLMClientError("Azure OpenAI response did not include choices")

    content = choices[0].get("message", {}).get("content")
    if not content:
        raise LLMClientError("Azure OpenAI response content was missing")

    return str(content)


def call_llm(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider in {"", "mock", "fallback", "none"}:
        raise LLMClientError("LLM provider is set to mock/fallback mode")
    if provider == "openai":
        return call_openai(messages)
    if provider == "azure_openai":
        return call_azure_openai(messages)
    if provider == "claude":
        return call_claude(messages)

    raise LLMClientError(f"Unsupported LLM provider: {settings.llm_provider}")
