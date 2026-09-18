"""LLM adapter with a local fallback."""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import get_settings


def complete_json(system: str, user: str) -> dict[str, Any] | None:
    raw = complete(system, user)
    if not raw:
        return None
    return extract_json(raw)


def complete(system: str, user: str) -> str | None:
    settings = get_settings()
    provider = settings.resolved_provider
    if provider == "local":
        return None
    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage

            model = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.openai_api_key,
                temperature=0.1,
                timeout=60,
            )
            response = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            return str(response.content)
        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage, SystemMessage

            model = ChatAnthropic(
                model=settings.llm_model if "claude" in settings.llm_model else "claude-3-5-sonnet-latest",
                api_key=settings.anthropic_api_key,
                temperature=0.1,
                timeout=60,
            )
            response = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            return str(response.content)
    except Exception:
        return None
    return None


def extract_json(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
