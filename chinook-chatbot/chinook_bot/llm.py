"""OpenAI-compatible client (OpenAI, local Ollama, or Ollama Cloud)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OLLAMA_CLOUD_V1 = "https://ollama.com/v1"
OLLAMA_LOCAL_V1 = "http://localhost:11434/v1"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def base_url() -> str | None:
    explicit = os.getenv("OPENAI_BASE_URL") or os.getenv("OLLAMA_HOST")
    if explicit:
        url = explicit.rstrip("/")
        if url.endswith("/v1"):
            return url
        if "localhost:11434" in url or url.endswith(":11434"):
            return url + "/v1"
        return url
    if os.getenv("OLLAMA_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        return OLLAMA_CLOUD_V1
    return None


def api_key() -> str:
    key = os.getenv("OPENAI_API_KEY") or os.getenv("OLLAMA_API_KEY")
    if key:
        return key
    if base_url() and "localhost:11434" in (base_url() or ""):
        return "ollama"
    raise RuntimeError(
        "No API key set. For Ollama Cloud, set OLLAMA_API_KEY. "
        "For a local Ollama app signed into cloud, set "
        "OPENAI_BASE_URL=http://localhost:11434/v1 and OPENAI_API_KEY=ollama. "
        "For OpenAI, set OPENAI_API_KEY."
    )


def get_client() -> OpenAI:
    kwargs: dict[str, Any] = {"api_key": api_key()}
    url = base_url()
    if url:
        kwargs["base_url"] = url
    return OpenAI(**kwargs)


def model_name() -> str:
    return os.getenv("OPENAI_MODEL") or os.getenv("OLLAMA_MODEL") or "gpt-4o-mini"


def uses_ollama() -> bool:
    url = (base_url() or "").lower()
    return "ollama.com" in url or "11434" in url or bool(os.getenv("OLLAMA_API_KEY"))


def _parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("No JSON object found", cleaned, 0)
    return json.loads(cleaned[start : end + 1])


def complete_json(system: str, user: str, history: list[dict] | None = None) -> dict:
    client = get_client()
    json_system = (
        system
        + "\n\nRespond with a single JSON object only. No markdown fences, no extra text."
    )
    messages: list[dict] = [{"role": "system", "content": json_system}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": user})

    kwargs: dict[str, Any] = {
        "model": model_name(),
        "temperature": 0,
        "messages": messages,
    }
    json_mode = os.getenv("LLM_JSON_MODE")
    use_json_mode = _truthy(json_mode) if json_mode is not None else not uses_ollama()
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or "{}"
    return _parse_json_object(content)


def complete_text(system: str, user: str) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model=model_name(),
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (response.choices[0].message.content or "").strip()
