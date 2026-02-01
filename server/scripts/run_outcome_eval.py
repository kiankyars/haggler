"""Run Weave Evaluation for the haggler outcome classifier.

Uses the same evaluator as the bot (Gemini) so you can:
- Version eval datasets and compare runs in W&B
- Tune the eval prompt/model against human-labeled outcomes
- Track scorer metrics (e.g. correct vs expected_outcome)

Requires: WANDB_API_KEY, GOOGLE_API_KEY (for the classifier).
Run from server dir: uv run scripts/run_outcome_eval.py
Set WANDB_API_KEY and GOOGLE_API_KEY (e.g. in .env).
"""

import asyncio
import os
import sys
from pathlib import Path

# So "from bot import ..." works when run as scripts/run_outcome_eval.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import weave
from dotenv import load_dotenv
from weave import Evaluation, Model

load_dotenv(override=True)

from bot import _evaluate_outcome

# Small curated set: add rows with transcript + expected_outcome (success/failure)
# so the scorer can measure classifier accuracy. Extend or load from CSV/Weave dataset.
OUTCOME_EXAMPLES = [
    {
        "transcript": "user: Sorry, we cannot offer a refund after 30 days.\nassistant: I've been a loyal customer for 10 years. Can I speak to a supervisor?\nuser: I've approved a one-time refund to your original payment method.\nassistant: Thank you.",
        "mode": "refund",
        "expected_outcome": "success",
    },
    {
        "transcript": "user: Our policy is no refunds.\nassistant: What can you do instead, like a credit or voucher?\nuser: I can add a 50 dollar travel credit to your account.\nassistant: I'll take that.",
        "mode": "refund",
        "expected_outcome": "success",
    },
    {
        "transcript": "user: No refunds are possible. Is there anything else?\nassistant: I understand. I'll look at other options.\nuser: Goodbye.",
        "mode": "refund",
        "expected_outcome": "failure",
    },
    {
        "transcript": "user: We don't offer discounts on this rate.\nassistant: I'm negotiating for a better deal. Can you check with retention?\nuser: I've applied a 15% discount to your booking.\nassistant: Thanks.",
        "mode": "negotiation",
        "expected_outcome": "success",
    },
]


@weave.op()
def outcome_scorer(expected_outcome: str, output: dict) -> dict:
    pred = (output.get("outcome") or "").strip().lower()
    exp = (expected_outcome or "").strip().lower()
    return {"correct": pred == exp}


class OutcomeModel(Model):
    """Wraps the bot's _evaluate_outcome so we can run Weave Evaluation."""

    @weave.op()
    def predict(self, transcript: str, mode: str) -> dict:
        outcome = _evaluate_outcome(transcript, mode)
        return {"outcome": outcome}


def main() -> None:
    if not os.environ.get("WANDB_API_KEY"):
        print("WANDB_API_KEY is not set. Set it to run evals (e.g. from https://wandb.ai/authorize).")
        raise SystemExit(1)
    if not os.environ.get("GOOGLE_API_KEY"):
        print("GOOGLE_API_KEY is not set. The classifier uses Gemini.")
        raise SystemExit(1)

    project = os.getenv("WEAVE_PROJECT", "factorio/haggler")
    weave.init(project)

    evaluation = Evaluation(
        name="haggler-outcome-eval",
        dataset=OUTCOME_EXAMPLES,
        scorers=[outcome_scorer],
    )
    model = OutcomeModel()
    asyncio.run(evaluation.evaluate(model))
    print("Eval done. Check the run in W&B.")


if __name__ == "__main__":
    main()
