"""Shared chat helper. Prefers Claude; OpenAI is fallback if Anthropic is unset."""
from __future__ import annotations

import os
from typing import Any

from src.env_bootstrap import load_env_files

load_env_files()


def llm_configured() -> bool:
    return bool(
        (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    )


def _settings() -> tuple[str, str, str]:
    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if anthropic_key:
        model = (
            os.environ.get("AN_MODEL")
            or os.environ.get("GP_LLM_MODEL")
            or "claude-sonnet-4-5"
        ).strip()
        return "anthropic", anthropic_key, model
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if openai_key:
        model = (os.environ.get("OPENAI_API_MODEL") or "gpt-4o-mini").strip()
        return "openai", openai_key, model
    raise RuntimeError("ANTHROPIC_API_KEY missing")


def _anthropic_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts).strip()


def _anthropic_messages_create(client: Any, **kwargs: Any) -> Any:
    try:
        return client.messages.create(**kwargs)
    except TypeError:
        for key in ("temperature", "top_p", "top_k"):
            kwargs.pop(key, None)
        return client.messages.create(**kwargs)


def chat_complete(
    *,
    system: str,
    user: str,
    timeout: float,
    temperature: float,
    max_tokens: int,
    json_object: bool = False,
) -> str:
    provider, api_key, model = _settings()
    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key, timeout=timeout)
        prompt = system
        if json_object and "JSON" not in system:
            prompt = system + "\nReply with ONLY a JSON object. No markdown."
        response = _anthropic_messages_create(
            client,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=prompt,
            messages=[{"role": "user", "content": user}],
        )
        return _anthropic_text(response)

    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=timeout)
    kwargs: dict = {}
    if json_object:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return (response.choices[0].message.content or "").strip()
