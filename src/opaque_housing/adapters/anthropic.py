"""Anthropic Messages API. Network only; classification merge stays pure."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from opaque_housing.adapters.http import user_agent
from opaque_housing.classify.llm import SYSTEM_PROMPT, LlmLabel, parse_llm_json

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# USD per million tokens. Unknown models use the Sonnet pair so a cap still binds.
_PRICE_IN = (("haiku", 0.25), ("opus", 15.0), ("sonnet", 3.0))
_PRICE_OUT = (("haiku", 1.25), ("opus", 75.0), ("sonnet", 15.0))


@dataclass
class LlmUsage:
    names: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0


class CostCapExceeded(RuntimeError):
    pass


def model_id_from_env() -> str:
    model = os.environ.get("ANTHROPIC_MODEL", "").strip()
    if not model:
        raise RuntimeError("ANTHROPIC_MODEL is not set")
    return model


def api_key_from_env() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return key


def price_per_mtok(model: str) -> tuple[float, float]:
    lower = model.lower()
    pin = next((price for token, price in _PRICE_IN if token in lower), 3.0)
    pout = next((price for token, price in _PRICE_OUT if token in lower), 15.0)
    return pin, pout


def estimate_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = price_per_mtok(model)
    return (input_tokens / 1_000_000.0) * pin + (output_tokens / 1_000_000.0) * pout


class AnthropicClassifier:
    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        http: httpx.Client | None = None,
        cost_cap_usd: float = 5.0,
        max_names: int = 500,
        sender: Callable[[str], tuple[object, int, int]] | None = None,
    ) -> None:
        self.model = model or model_id_from_env()
        self.api_key = api_key if api_key is not None else api_key_from_env()
        self.cost_cap_usd = cost_cap_usd
        self.max_names = max_names
        self.usage = LlmUsage()
        self._http = http
        self._sender = sender

    def classify_name(self, name_normalized: str) -> LlmLabel:
        if self.usage.names >= self.max_names:
            raise CostCapExceeded(f"LLM name cap {self.max_names} reached")
        if self.usage.usd >= self.cost_cap_usd:
            raise CostCapExceeded(f"LLM cost cap ${self.cost_cap_usd:.2f} reached")
        payload, input_tokens, output_tokens = self._complete(name_normalized)
        usd = estimate_usd(self.model, input_tokens, output_tokens)
        if self.usage.usd + usd > self.cost_cap_usd:
            raise CostCapExceeded(f"LLM cost cap ${self.cost_cap_usd:.2f} would be exceeded")
        label = parse_llm_json(payload, model_id=self.model)
        self.usage.names += 1
        self.usage.input_tokens += input_tokens
        self.usage.output_tokens += output_tokens
        self.usage.usd += usd
        return LlmLabel(
            owner_class=label.owner_class,
            rationale=label.rationale,
            model_id=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _complete(self, name_normalized: str) -> tuple[object, int, int]:
        if self._sender is not None:
            return self._sender(name_normalized)
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
            "user-agent": user_agent(),
        }
        body = {
            "model": self.model,
            "max_tokens": 256,
            "temperature": 0,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": name_normalized}],
        }
        own = self._http is None
        session = self._http or httpx.Client(timeout=60.0)
        try:
            response = session.post(ANTHROPIC_URL, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
        finally:
            if own:
                session.close()
        text = ""
        for block in data.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                text += str(block.get("text") or "")
        usage = data.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM did not return JSON") from exc
        return payload, input_tokens, output_tokens
