"""The prompt schemas, which had no tests.

These schemas are passed to the Claude API as `output_config.format`, so the
API itself rejects a malformed one at request time -- meaning a mistake here
surfaces as a failed analysis rather than a failed test. Strict structured
outputs also require `additionalProperties: false` and a complete `required`
list at every object level, which is easy to break when adding a field.

The EMPTY_* fallbacks in claim_extractor must also match their schema, since
consistency_checker reads those keys unconditionally.
"""

import pytest

from src.llm import prompts
from src.nlp.claim_extractor import EMPTY_CLAIMS, EMPTY_OBSERVATIONS

SCHEMAS = {
    "claim_extraction": prompts.CLAIM_EXTRACTION_SCHEMA,
    "figure_vision": prompts.FIGURE_VISION_SCHEMA,
}


def _objects(node):
    """Yield every object-typed subschema, including nested ones."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield node
        for value in node.values():
            yield from _objects(value)
    elif isinstance(node, list):
        for item in node:
            yield from _objects(item)


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_every_object_level_is_strict(name):
    """Structured outputs need additionalProperties:false at every level."""
    for obj in _objects(SCHEMAS[name]):
        assert obj.get("additionalProperties") is False, (
            f"{name}: an object level allows additional properties")


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_required_lists_every_declared_property(name):
    """Strict mode requires every property to be listed in `required`."""
    for obj in _objects(SCHEMAS[name]):
        properties = set(obj.get("properties", {}))
        required = set(obj.get("required", []))
        assert properties == required, (
            f"{name}: required != properties "
            f"(missing {sorted(properties - required)}, "
            f"extra {sorted(required - properties)})")


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_every_property_is_documented(name):
    for obj in _objects(SCHEMAS[name]):
        for prop, spec in obj.get("properties", {}).items():
            assert spec.get("description"), (
                f"{name}.{prop} has no description; the model relies on it")


def test_empty_claims_matches_the_claim_schema():
    """consistency_checker reads these keys whether or not the LLM ran."""
    assert set(EMPTY_CLAIMS) == set(
        prompts.CLAIM_EXTRACTION_SCHEMA["properties"])


def test_empty_observations_matches_the_vision_schema():
    assert set(EMPTY_OBSERVATIONS) == set(
        prompts.FIGURE_VISION_SCHEMA["properties"])


# ------------------------------------------------------------------ prompts
def test_claim_prompt_includes_the_label_caption_and_context():
    prompt = prompts.build_claim_extraction_prompt(
        "Figure 3", "A western blot of protein X.", "As shown in Figure 3, ...")
    assert "Figure 3" in prompt
    assert "A western blot of protein X." in prompt
    assert "As shown in Figure 3" in prompt


def test_vision_prompt_includes_the_label_and_caption():
    prompt = prompts.build_figure_vision_prompt("Figure 2", "Microscopy.")
    assert "Figure 2" in prompt
    assert "Microscopy." in prompt


def test_prompts_tolerate_empty_text():
    assert prompts.build_claim_extraction_prompt("Figure 1", "", "").strip()
    assert prompts.build_figure_vision_prompt("Figure 1", "").strip()


def test_systems_are_non_empty():
    assert prompts.CLAIM_EXTRACTION_SYSTEM.strip()
    assert prompts.FIGURE_VISION_SYSTEM.strip()
