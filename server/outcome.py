"""Single outcome classifier for haggler: success vs failure.

Used by:
- bot.py: at session end, outcome from W&B eval model; run Weave Evaluation after each run; Redis from eval outcome.
- run_outcome_eval.py: Weave Evaluation on dataset (seed + live examples from bot).

One prompt, one parse. Eval runs after each run via W&B mechanism.
"""

# Weave Dataset name for outcome evals; bot adds row every run; run_outcome_eval runs Evaluation on it
OUTCOME_DATASET_NAME = "haggler-outcome-examples"

import asyncio
import os
from typing import Literal

import weave
from openai import OpenAI
from pydantic import PrivateAttr
from weave import Dataset, Evaluation, Model

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


@weave.op()
def outcome_scorer(expected_outcome: str, output: dict) -> dict:
    pred = (output.get("outcome") or "").strip().lower()
    exp = (expected_outcome or "").strip().lower()
    return {"correct": pred == exp}


class OutcomeModel(Model):
    """Same prompt as outcome.py; used by Weave Evaluation and by bot for outcome."""
    prompt: weave.Prompt = weave.StringPrompt(OUTCOME_SYSTEM)
    model: str = "OpenPipe/Qwen3-14B-Instruct"
    _client: OpenAI = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._client = OpenAI(
            base_url="https://api.inference.wandb.ai/v1",
            api_key=os.environ["WANDB_API_KEY"],
            project=os.getenv("WEAVE_PROJECT", "factorio/haggler"),
        )

    @weave.op
    def predict(self, transcript: str, mode: str) -> dict:
        if not transcript.strip():
            return {"outcome": "failure"}
        goal = goal_for_mode(mode)
        user_content = f"The customer was {goal}. Answer with exactly one word: success or failure.\n\nTranscript:\n{transcript}"
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.prompt.format()},
                {"role": "user", "content": user_content},
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        outcome = parse_outcome(raw)
        return {"outcome": outcome}


def evaluate_outcome_wandb(transcript: str, mode: str) -> Literal["success", "failure"]:
    """Classify outcome using W&B Inference (same model as Weave Evaluation). Used by bot when WANDB_API_KEY set."""
    if not transcript.strip():
        return "failure"
    if not os.environ.get("WANDB_API_KEY"):
        return "failure"
    return OutcomeModel().predict(transcript, mode)["outcome"]  # type: ignore


def run_single_row_eval_sync(transcript: str, mode: str, expected_outcome: str) -> None:
    """Run Weave Evaluation on this one row (W&B eval after each run). weave.init(project) must already be called."""
    row = {"transcript": transcript, "mode": mode, "expected_outcome": expected_outcome}
    evaluation = Evaluation(
        dataset=[row],
        scorers=[outcome_scorer],
        evaluation_name="haggler-outcome-eval",
    )
    model = OutcomeModel()
    asyncio.run(evaluation.evaluate(model))


TACTIC_SUGGEST_SYSTEM = (
    "You are analyzing a successful voice call. In the transcript, the customer is the 'assistant', support is the 'user'. "
    "Based on what worked in this call, suggest exactly one new tactic that could help in similar situations. "
    "Output only the tactic text, one clear sentence, no preamble or numbering."
)


def suggest_tactic_wandb(transcript: str, mode: str) -> str:
    """Suggest one new tactic from successful call using W&B Inference (avoids Gemini quota)."""
    if not transcript.strip() or not os.environ.get("WANDB_API_KEY"):
        return ""
    goal = "refund" if mode == "refund" else "negotiation (discount/booking/deal)"
    user_content = (
        f"The customer got what they wanted ({goal}).\n\nTranscript:\n{transcript}"
    )
    client = OpenAI(
        base_url="https://api.inference.wandb.ai/v1",
        api_key=os.environ["WANDB_API_KEY"],
        project=os.getenv("WEAVE_PROJECT", "factorio/haggler"),
    )
    response = client.chat.completions.create(
        model="OpenPipe/Qwen3-14B-Instruct",
        messages=[
            {"role": "system", "content": TACTIC_SUGGEST_SYSTEM},
            {"role": "user", "content": user_content},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    return text


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
