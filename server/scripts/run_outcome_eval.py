"""Run Weave Evaluation for the haggler outcome classifier.

Uses same prompt/parse as bot (outcome.py). Benchmarks classifier on a golden dataset in W&B.
Requires: WANDB_API_KEY. Run from server dir: uv run scripts/run_outcome_eval.py
"""

import asyncio
import os
import sys

import weave
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import PrivateAttr
from weave import Evaluation, Model

# server/ on path so outcome is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from outcome import OUTCOME_SYSTEM, goal_for_mode, parse_outcome

load_dotenv(override=True)

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
    """Same prompt as bot (outcome.py). Eval validates production classifier."""
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


def main() -> None:
    if not os.environ.get("WANDB_API_KEY"):
        print("WANDB_API_KEY is not set (e.g. https://wandb.ai/authorize).")
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
