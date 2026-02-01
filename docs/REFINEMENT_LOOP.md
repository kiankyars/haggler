# Refinement Loop

How the haggler bot learns from each voice session and improves over time.

---

## How we evaluate success of a trace

We don’t use human labels at runtime. When you disconnect from a call, the bot:

1. **Gets the transcript** – All messages from the voice call (user = you/support, assistant = the bot/customer) are read from `LLMContext` and formatted as text.

2. **Calls an LLM judge** – `_evaluate_outcome(transcript, mode)` in `bot.py` sends that transcript to **Gemini** with a fixed prompt that says:
   - In the transcript, the **customer** is the `assistant`, the **support/agent** is the `user`.
   - The customer was either “seeking a refund” or “negotiating (discount/booking/deal)” (from `HAGGLER_MODE`).
   - “Did the customer get what they wanted (refund granted, deal agreed, discount given, etc.)?”
   - “Answer with exactly one word: **success** or **failure**.”

3. **Uses the one-word answer** – Gemini returns “success” or “failure”. That becomes the **outcome** for this session. No ground truth is involved; it’s **LLM-as-judge**: the same LLM decides whether the transcript describes a successful outcome for the customer.

4. **Logs to Weave** – `log_session_end(session_id, config, duration_seconds, outcome)` is a Weave op. It logs `outcome` and a **score** (1.0 for success, 0.0 for failure) so each trace in W&B shows how that session was classified.

5. **Updates Redis** – If outcome is **success**, tactics from this session are merged into `agent:winning_tactics`. If **failure**, they’re appended (deduped) to `agent:failed_tactics`.

So “success” = the LLM judge decided the customer got what they wanted from the transcript. You can tune the judge by changing the prompt or model (e.g. `GOOGLE_EVAL_MODEL`). To check how accurate the judge is, use **`scripts/run_outcome_eval.py`**: that script has a small dataset of transcripts with **human-labeled** `expected_outcome` and scores the judge’s predictions against those labels.

---

## 1. Data sources (Redis)

| Key | Role |
|-----|------|
| **`agent:tactics`** | Base tactics list (you seed once, e.g. via `redis-cli`). Never overwritten by the bot. |
| **`agent:winning_tactics`** | Tactics that appeared in sessions the evaluator scored as **success**. Prepended to the prompt on the next run. |
| **`agent:failed_tactics`** | Tactics that appeared in sessions scored as **failure**, excluding any that are in `agent:tactics` (base tactics are never stored here). Deduplicated; used for analysis / evals, not fed back into the prompt. |
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

- **Adding new base tactics**  
  - `scripts/add_tactics.py` appends tactics to `agent:tactics` (deduplicated). Usage:  
    `uv run python scripts/add_tactics.py "Tactic one." "Tactic two."`  
    or `--file path` (one tactic per line), or pipe lines via stdin.

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
