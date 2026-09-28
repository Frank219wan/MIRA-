"""Provider-independent instruction for the Week 1 tutorial-video PoC."""

TUTORIAL_PROMPT_VERSION = "week1-v1"

TUTORIAL_PARSER_PROMPT = """You analyze one eye-makeup tutorial video or its ordered frames.
Identify the five main, observable application actions in chronological order.
Return JSON only in this shape:
{"action_units": [{"step_index": 1, "area": "...", "goal": "...",
"product_requirement": "...", "tool": "...", "motion": "...",
"intensity": "...", "target_result": "...",
"time_range_seconds": [0.0, 1.0], "confidence": 0.0}]}
There must be exactly five action_units with step_index values 1, 2, 3, 4, 5.
Describe only visible tutorial actions. Do not infer face shape, eye type,
personal suitability, or beauty conclusions.
"""
