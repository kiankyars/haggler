# Refinement Loop

How the haggler bot learns from each voice session and improves over time.

---

## 1. Data sources (Redis)

| Key | Role |
|-----|------|
| **`agent:tactics`** | Base tactics list (you seed once, e.g. via `redis-cli`). Never overwritten by the bot. |
| **`agent:winning_tactics`** | Tactics that appeared in sessions the evaluator scored as **success**. Prepended to the prompt on the next run. |
| **`agent:failed_tactics`** | Tactics that appeared in sessions scored as **failure**. Deduplicated; used for analysis / evals, not fed back into the prompt. |
| **`session:<uuid>:tactics`** | Per-session snapshot of the tactics used in that call. TTL 24h; deleted after merge or on failure write. |

---

## 2. Per-session flow (bot.py)

1. **Session start**  
   - `get_session_config(session_id)` runs (and is traced in Weave).  
   - It reads Redis: **winning_tactics** first, then **tactics**, merged and deduplicated.  
   - That list becomes “Winning tactics to use when appropriate” in the system instruction for Gemini.  
   - Pipeline runs: you (support) talk to the bot (customer) over WebRTC.

2. **Session end (on_client_disconnected)**  
   - Transcript is taken from `LLMContext`.  
   - **Outcome** is computed by `_evaluate_outcome(transcript, mode)` (Gemini): one word, `success` or `failure`.  
   - If Weave is configured: `log_session_end(session_id, config, duration_seconds, outcome)` is called → trace gets `outcome` and `score` (1.0 / 0.0).  
   - Redis is updated:
     - Current session’s tactics are written to `session:<session_id>:tactics` (then key is deleted after use).
     - **If success:** `_merge_winning_tactics()` appends any *new* tactics from this session into `agent:winning_tactics` (no duplicates).  
     - **If failure:** each tactic from this session is appended to `agent:failed_tactics` only if not already there (deduplicated).

So: **success** → tactics from that session are promoted into **winning_tactics** and used earlier in future prompts. **Failure** → tactics are recorded in **failed_tactics** for inspection/evals only; the prompt for the next session is still **winning_tactics + tactics**.

---

## 3. Observability and evals

- **Weave (W&B)**  
  - `get_session_config` and `log_session_end` are `@weave.op()`.  
  - Each session produces a trace with config, duration, and the auto-evaluated **outcome** and **score**.  
  - Lets you inspect which sessions were scored success/failure and compare over time.

- **Outcome eval script** (`scripts/run_outcome_eval.py`)  
  - Uses **Weave Evaluation** + **W&B Inference** (no Gemini).  
  - Dataset: list of `{transcript, mode, expected_outcome}`.  
  - Model: same *task* as `_evaluate_outcome` (classify success/failure) but implemented with W&B Inference so you can version prompts/models and compare runs in W&B.  
  - Scorer: `correct` = (predicted outcome == expected_outcome).  
  - Run: `uv run scripts/run_outcome_eval.py` (from `server/`).  
  - This **evaluates the classifier**, not the voice bot itself; it helps you tune the outcome model and add gold labels.

- **Redis state**  
  - `scripts/check_redis_improvement.py` prints `agent:tactics`, `agent:winning_tactics`, `agent:failed_tactics`, and `session:*:tactics` so you can see what the refinement loop has stored.

---

## 4. End-to-end refinement loop (summary)

```
Seed agent:tactics (once)
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  Session start: get_session_config()                            │
│  → Read winning_tactics + tactics from Redis                    │
│  → Build system instruction: base + "Winning tactics: …"         │
│  → Voice call (Pipecat/Gemini)                                  │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
  User disconnects
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  _evaluate_outcome(transcript, mode) → "success" | "failure"     │
│  log_session_end(...) → Weave trace (outcome, score)            │
│  Write session:<id>:tactics = tactics used this session         │
└─────────────────────────────────────────────────────────────────┘
        │
        ├── success ──► _merge_winning_tactics() → append new tactics to agent:winning_tactics
        │
        └── failure ──► append (dedup) to agent:failed_tactics
        │
        ▼
  Next session uses updated winning_tactics + tactics → refinement loop repeats.
```

The **only** thing that changes between sessions is the contents of **winning_tactics** (and **failed_tactics** for analytics). Base **tactics** stay fixed unless you change them in Redis.
