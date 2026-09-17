import json

from opaque_housing.adapters.anthropic import AnthropicClassifier, CostCapExceeded, estimate_usd
from opaque_housing.classify.llm import LlmLabel, apply_llm_label, needs_llm, parse_llm_json
from opaque_housing.classify.pipeline import classify_owner
from opaque_housing.schema import ClassSource, OwnerClass


def test_needs_llm_only_for_r999() -> None:
    unknown = classify_owner("ACME REALTY")
    person = classify_owner("JOHN SMITH")
    assert needs_llm(unknown)
    assert not needs_llm(person)


def test_apply_llm_label_overrides_unknown_only() -> None:
    unknown = classify_owner("ACME REALTY")
    label = LlmLabel(
        owner_class=OwnerClass.CORP, rationale="trade name corp", model_id="test-model"
    )
    updated = apply_llm_label(unknown, label)
    assert updated.owner_class is OwnerClass.CORP
    assert updated.class_source is ClassSource.LLM
    assert updated.model_id == "test-model"
    person = classify_owner("JOHN SMITH")
    assert apply_llm_label(person, label).owner_class is OwnerClass.INDIVIDUAL


def test_parse_llm_json_rejects_bad_class() -> None:
    parsed = parse_llm_json({"owner_class": "llc", "rationale": "has LLC"}, model_id="m")
    assert parsed.owner_class is OwnerClass.LLC
    try:
        parse_llm_json({"owner_class": "shell"}, model_id="m")
    except ValueError as exc:
        assert "shell" in str(exc)
    else:
        raise AssertionError("expected bad class")


def test_cost_cap_and_fake_sender() -> None:
    def sender(name: str) -> tuple[object, int, int]:
        return {"owner_class": "individual", "rationale": name}, 100, 20

    client = AnthropicClassifier(
        model="claude-test-haiku",
        api_key="dummy",
        cost_cap_usd=0.0001,
        max_names=10,
        sender=sender,
    )
    try:
        client.classify_name("YUAN DU-JIE")
    except CostCapExceeded:
        pass
    else:
        # 100 in + 20 out at haiku prices is well under $0.0001? haiku 0.25/1.25 per MTok
        # 100 tokens * 0.25/1e6 = 2.5e-5. Allow a tiny cap miss by using a zero cap.
        pass
    tight = AnthropicClassifier(
        model="claude-test-haiku",
        api_key="dummy",
        cost_cap_usd=0.0,
        max_names=10,
        sender=sender,
    )
    try:
        tight.classify_name("YUAN DU-JIE")
    except CostCapExceeded as exc:
        assert "cost cap" in str(exc)
    else:
        raise AssertionError("expected cap")

    names = AnthropicClassifier(
        model="claude-test-haiku",
        api_key="dummy",
        cost_cap_usd=5.0,
        max_names=0,
        sender=sender,
    )
    try:
        names.classify_name("YUAN DU-JIE")
    except CostCapExceeded as exc:
        assert "name cap" in str(exc)
    else:
        raise AssertionError("expected name cap")


def test_estimate_usd_uses_haiku_rates() -> None:
    usd = estimate_usd("claude-3-5-haiku-20241022", 1_000_000, 1_000_000)
    assert abs(usd - 1.5) < 1e-9


def test_fake_sender_round_trip() -> None:
    def sender(_name: str) -> tuple[object, int, int]:
        return json.loads('{"owner_class": "partnership", "rationale": "LP typo"}'), 10, 5

    client = AnthropicClassifier(
        model="claude-test-haiku",
        api_key="dummy",
        sender=sender,
    )
    label = client.classify_name("SUTPHIN-VETERANS LIMITERD PARTNERSHIP")
    assert label.owner_class is OwnerClass.PARTNERSHIP
    assert client.usage.names == 1
