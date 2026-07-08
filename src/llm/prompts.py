"""LLM prompt templates + JSON schemas, kept separate for easy editing.

Each extraction task pairs a natural-language prompt with a strict JSON
Schema. The schema is passed to the Claude API via ``output_config.format``
(structured outputs), which *guarantees* the response validates against it —
far more reliable than asking for JSON in prose and hoping. Keep the prompt
and schema in sync when editing.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Claim extraction: pull structured, checkable claims about ONE figure from
# its caption + the surrounding results/methods text.
# --------------------------------------------------------------------------
CLAIM_EXTRACTION_SYSTEM = (
    "You are a meticulous scientific-integrity analyst. You extract only "
    "claims that are explicitly stated in the provided text about a specific "
    "figure — you never infer, guess, or add facts that are not written. "
    "When a value is not stated, you leave it null. You are precise about "
    "numbers, sample sizes, and statistical values."
)

# The schema the model MUST return. `additionalProperties: false` + `required`
# on every level is required for strict structured outputs.
CLAIM_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "claimed_description": {
            "type": ["string", "null"],
            "description": "One-sentence summary of what the text says the "
                           "figure depicts (e.g. 'Western blot of protein X "
                           "across 4 treatment conditions'). Null if not stated.",
        },
        "claimed_n": {
            "type": ["integer", "null"],
            "description": "The sample size / number of independent replicates "
                           "explicitly stated for this figure (the 'n='). Null "
                           "if not stated.",
        },
        "claimed_panel_count": {
            "type": ["integer", "null"],
            "description": "Number of distinct visual elements the text says the "
                           "figure shows — lanes, bands, panels, conditions, "
                           "groups, or bars. Null if not stated.",
        },
        "panel_count_kind": {
            "type": ["string", "null"],
            "enum": ["lanes", "bands", "panels", "conditions", "groups", "bars", None],
            "description": "What the claimed_panel_count counts. Null if no "
                           "count was stated.",
        },
        "claimed_stats": {
            "type": "array",
            "description": "Every statistical value explicitly reported for this "
                           "figure.",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["p_value", "fold_change", "percent",
                                 "correlation", "ratio", "other"],
                    },
                    "value": {
                        "type": "number",
                        "description": "The numeric value as written.",
                    },
                    "raw_text": {
                        "type": "string",
                        "description": "The exact phrase from the text, e.g. "
                                       "'p < 0.001' or '2.5-fold increase'.",
                    },
                },
                "required": ["kind", "value", "raw_text"],
                "additionalProperties": False,
            },
        },
        "error_bar_description": {
            "type": ["string", "null"],
            "description": "How error bars are described (e.g. 'mean ± SEM', "
                           "'95% CI'). Null if not described.",
        },
    },
    "required": [
        "claimed_description", "claimed_n", "claimed_panel_count",
        "panel_count_kind", "claimed_stats", "error_bar_description",
    ],
    "additionalProperties": False,
}


def build_claim_extraction_prompt(figure_label: str, caption: str,
                                  results_text: str) -> str:
    """Assemble the user prompt for extracting claims about one figure."""
    results_block = results_text.strip() or "(no additional results text found)"
    return (
        f"Extract the checkable claims that the following paper text makes "
        f"about **{figure_label}**. Use ONLY what is written; if a field is "
        f"not stated, return null (or an empty list for claimed_stats).\n\n"
        f"=== FIGURE CAPTION ===\n{caption.strip()}\n\n"
        f"=== SURROUNDING RESULTS / METHODS TEXT ===\n{results_block}\n\n"
        f"Return the structured claims for {figure_label}."
    )
