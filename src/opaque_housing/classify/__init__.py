"""Owner-class rules and LLM fallback."""

from opaque_housing.classify.pipeline import classify_owner
from opaque_housing.classify.rules import RULES_VERSION

__all__ = ["RULES_VERSION", "classify_owner"]
