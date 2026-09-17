"""LLM fallback helpers. Prompt + merge are pure; HTTP lives in adapters."""

from __future__ import annotations

from dataclasses import dataclass

from opaque_housing.schema import ClassSource, Owner, OwnerClass

PROMPT_VERSION = "2026-09-17.1"

SYSTEM_PROMPT = """You classify a US property-owner name into exactly one class.
Return JSON only: {"owner_class": "<class>", "rationale": "<one line>"}
Classes: individual, trust, estate, llc, corp, partnership, coop_corp,
hdfc, public, nonprofit_religious, lender_reo, unknown
- LLC or limited liability → llc
- Inc, Corp, Ltd, Company → corp
- LP, LLP, partnership → partnership
- Trust or trustee → trust
- Estate of → estate
- Co-op, tenants corp, owners corp → coop_corp
- HDFC or housing development fund → hdfc
- Government agencies → public
- Churches, universities, hospitals, nonprofits → nonprofit_religious
- Banks, GSEs, mortgage servicers → lender_reo
- A natural person or married couple → individual
- If you cannot tell, unknown
Use the name only. Do not invent facts."""

NEEDS_LLM_RULE = "R999_unknown"


@dataclass(frozen=True)
class LlmLabel:
    owner_class: OwnerClass
    rationale: str
    model_id: str
    prompt_version: str = PROMPT_VERSION
    input_tokens: int = 0
    output_tokens: int = 0
    confidence: float = 0.6


def needs_llm(owner: Owner) -> bool:
    return owner.owner_class is OwnerClass.UNKNOWN and owner.rule_id == NEEDS_LLM_RULE


def apply_llm_label(owner: Owner, label: LlmLabel | None) -> Owner:
    if not needs_llm(owner) or label is None:
        return owner
    return owner.model_copy(
        update={
            "owner_class": label.owner_class,
            "class_source": ClassSource.LLM,
            "model_id": label.model_id,
            "prompt_version": label.prompt_version,
            "confidence": label.confidence,
        }
    )


def parse_llm_json(payload: object, *, model_id: str) -> LlmLabel:
    if not isinstance(payload, dict):
        raise ValueError("LLM response is not an object")
    raw = str(payload.get("owner_class") or "").strip().lower()
    try:
        owner_class = OwnerClass(raw)
    except ValueError as exc:
        raise ValueError(f"LLM returned unknown class {raw!r}") from exc
    rationale = str(payload.get("rationale") or "").strip()
    return LlmLabel(owner_class=owner_class, rationale=rationale, model_id=model_id)
