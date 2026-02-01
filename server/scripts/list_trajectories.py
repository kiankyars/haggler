#!/usr/bin/env python3
"""List recent haggler trajectories (log_session_end calls) from Weave/W&B.

Run from server/: uv run python scripts/list_trajectories.py
Requires WANDB_API_KEY. Set WEAVE_PROJECT if not factorio/haggler.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

if not os.environ.get("WANDB_API_KEY"):
    print("WANDB_API_KEY not set.")
    sys.exit(1)

import weave

project = os.getenv("WEAVE_PROJECT", "factorio/haggler")
weave.init(project)
client = weave.get_client()

calls = client.get_calls(
    columns=["inputs", "output", "started_at", "op_name", "trace_id"],
    limit=50,
)
log_ends = [
    c
    for c in (calls or [])
    if "log_session_end" in str(getattr(c, "op_name", ""))
]
log_ends.sort(key=lambda c: getattr(c, "started_at", "") or "", reverse=True)

print(f"Recent trajectories (log_session_end) — {project}\n")
print(f"{'session_id':<12} {'outcome':<8} {'score':<6} {'transcript_len':<14} {'duration_sec':<12} trace_id")
print("-" * 70)
for c in log_ends[:25]:
    inp = getattr(c, "inputs", None) or {}
    dinp = dict(inp) if hasattr(inp, "items") else {}
    out = getattr(c, "output", None) or {}
    d = dict(out) if hasattr(out, "items") else {}
    sid = (dinp.get("session_id") or d.get("session_id") or "?")[:12]
    outcome = dinp.get("outcome") or d.get("outcome", "?")
    score = d.get("score", "?")
    tlen = dinp.get("transcript_length", "?")
    dur = dinp.get("duration_seconds")
    dur_s = f"{round(dur, 1)}" if isinstance(dur, (int, float)) else str(dur)
    trace_id = getattr(c, "trace_id", "") or ""
    print(f"{sid:<12} {outcome:<8} {score!s:<6} {tlen!s:<14} {dur_s:<12} {trace_id}")
    if tlen == 0 or tlen == "?":
        print("  (transcript empty or not logged — evaluator had no dialogue to judge)")
    elif dinp.get("transcript_preview"):
        print(f"  preview: {str(dinp['transcript_preview'])[:100]}...")
print("\nView traces: https://wandb.ai/factorio/haggler/weave")
