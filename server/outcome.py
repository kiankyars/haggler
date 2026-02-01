"""Single outcome classifier for haggler: success vs failure.

Used by:
- bot.py: at session end, to drive refinement loop (winning_tactics / failed_tactics).
- run_outcome_eval.py: Weave Evaluation on dataset (seed + live examples from bot).

One prompt, one parse. Eval validates what production uses.
"""

# Weave Dataset name for outcome evals; bot adds rows on success; run_outcome_eval runs Evaluation on it
OUTCOME_DATASET_NAME = "haggler-outcome-examples"

import os
from typing import Literal

# Canonical prompt; do not duplicate in bot or run_outcome_eval.
OUTCOME_SYSTEM = (
    "You are evaluating a voice call. The customer is the 'assistant' in the transcript; 'user' is support/agent. "
    "The transcript may be truncated at the end. If it shows the customer got what they wanted "
    "(refund granted, deal agreed, credit/voucher offered and accepted, etc.), answer success. "
    "Only answer failure if the transcript clearly shows no resolution or the customer did not get what they wanted."
)
OUTCOME_USER_TEMPLATE = (
    "The customer was {goal}. Answer with exactly one word: success or failure.\n\nTranscript:\n{transcript}"
)


def parse_outcome(raw: str) -> Literal["success", "failure"]:
    """Parse LLM output to success/failure. Same logic everywhere."""
    text = (raw or "").strip().lower()
    return "success" if "success" in text else "failure"


def goal_for_mode(mode: str) -> str:
    return "seeking a refund" if mode == "refund" else "negotiating (discount/booking/deal)"


def _outcome_prompt(transcript: str, mode: str) -> str:
    goal = goal_for_mode(mode)
    user_part = OUTCOME_USER_TEMPLATE.format(goal=goal, transcript=transcript)
    return f"{OUTCOME_SYSTEM}\n\n{user_part}"


def evaluate_outcome_gemini(transcript: str, mode: str) -> Literal["success", "failure"]:
    """Classify outcome using Gemini. Used by bot at session end."""
    if not transcript.strip():
        return "failure"
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "failure"
    from google import genai

    client = genai.Client(api_key=api_key)
    model = os.getenv("GOOGLE_EVAL_MODEL", "gemini-2.0-flash")
    prompt = _outcome_prompt(transcript, mode)
    response = client.models.generate_content(model=model, contents=prompt)
    text = getattr(response, "text", None) or ""
    if not text and getattr(response, "candidates", None):
        c = response.candidates[0] if response.candidates else None
        if c and getattr(c, "content", None) and c.content.parts:
            text = getattr(c.content.parts[0], "text", "") or ""
    return parse_outcome(text)
