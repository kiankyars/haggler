"""Run Weave Evaluation for the haggler outcome classifier (native W&B evals).

Uses Weave Dataset by name (seed + live examples added by bot). Same prompt/parse as bot (outcome.py).
Requires: WANDB_API_KEY. Run from server dir: uv run scripts/run_outcome_eval.py
Ref: https://docs.wandb.ai/weave/guides/core-types/evaluations
"""

import asyncio
import os
import sys

import weave
from dotenv import load_dotenv
from weave import Dataset, Evaluation

# server/ on path so outcome is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from outcome import OUTCOME_DATASET_NAME, OutcomeModel, outcome_scorer

load_dotenv(override=True)

# Seed examples; bootstrap dataset if not exists (bot adds row every run)
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


def _get_or_create_outcome_dataset():
    """Get Weave Dataset by name; create with seed examples if it doesn't exist."""
    ref = weave.ref(OUTCOME_DATASET_NAME)
    try:
        return ref.get()
    except Exception:
        dataset = Dataset(name=OUTCOME_DATASET_NAME, rows=OUTCOME_EXAMPLES)
        weave.publish(dataset, name=OUTCOME_DATASET_NAME)
        return dataset


def main() -> None:
    if not os.environ.get("WANDB_API_KEY"):
        print("WANDB_API_KEY is not set (e.g. https://wandb.ai/authorize).")
        raise SystemExit(1)

    project = os.getenv("WEAVE_PROJECT", "factorio/haggler")
    weave.init(project)

    dataset = _get_or_create_outcome_dataset()
    evaluation = Evaluation(
        dataset=dataset,
        scorers=[outcome_scorer],
        evaluation_name="haggler-outcome-eval",
    )
    model = OutcomeModel()
    asyncio.run(evaluation.evaluate(model))
    print("Eval done. Check the run in W&B.")


if __name__ == "__main__":
    main()
