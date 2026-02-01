# haggler

A Pipecat AI voice agent built with a realtime speech-to-speech pipeline.

## Configuration

- **Bot Type**: Web
- **Transport(s)**: SmallWebRTC
- **Pipeline**: Realtime
  - **Service**: Gemini Live
- **Modes**: `HAGGLER_MODE=refund` (default) or `negotiation` — refund agent (seeking refund) or negotiation agent (discount/booking/deal). You play the counterparty (support/other side); the agent “calls” you via the client.
- **Weave**: Session config traced at start; session end (config + duration) logged on disconnect. Set `WEAVE_PROJECT=factorio/haggler` so traces appear at [wandb.ai/factorio/haggler/weave/traces](https://wandb.ai/factorio/haggler/weave/traces). Each trace includes a **score** in the `log_session_end` op output (`outcome`: success/failure, `score`: 1.0 or 0.0). Tactics are updated from evals: success → `agent:winning_tactics`, failure → `agent:failed_tactics`. **Check project via wandb CLI:** `wandb login` then `wandb projects --entity factorio` or open https://wandb.ai/factorio/haggler. If you get "permission denied", create the project in W&B UI or unset `WANDB_API_KEY` to run without tracing.
- **Redis**: `agent:tactics` = tactics list; `agent:winning_tactics` = tactics that won (prepended next run); `agent:failed_tactics` = tactics from failed sessions (recorded for evals). Pre-seed: `LPUSH agent:tactics "your tactic"`. Self-improvement: on success merge into `agent:winning_tactics`; on failure append to `agent:failed_tactics`. Check state: `uv run python scripts/check_redis_improvement.py` (from `server/`). List recent trajectories (outcome/score): `uv run python scripts/list_trajectories.py`. Add base tactics: `uv run python scripts/add_tactics.py "Your tactic."` or `--file path`. **Refinement loop:** see [docs/REFINEMENT_LOOP.md](docs/REFINEMENT_LOOP.md).

## Setup

### Server

1. **Navigate to server directory**:

   ```bash
   cd server
   ```

2. **Install dependencies**:

   ```bash
   uv sync
   ```

3. **Configure environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

4. **Run the bot**:

   - SmallWebRTC: `uv run bot.py`

   If port 7860 is in use: `lsof -ti:7860 | xargs kill` (or stop the other process), then run again.

5. **Outcome & evals**: One outcome classifier in `server/outcome.py` (same prompt/parse everywhere). The bot uses it at session end to drive the refinement loop. **Weave evals (native):** Bot adds one example to the Weave Dataset after each successful negotiation; run `uv run scripts/run_outcome_eval.py` (from `server/`) once to bootstrap the dataset, then anytime to run the [Weave Evaluation](https://docs.wandb.ai/weave/guides/core-types/evaluations) on it (seed + live examples). No manual check—evals run in W&B.

### Client

1. **Navigate to client directory**:

   ```bash
   cd client
   ```

2. **Install dependencies**:

   ```bash
   npm install
   ```

3. **Configure environment variables**:

   ```bash
   cp env.example .env.local
   # Edit .env.local if needed (defaults to localhost:7860)
   ```


4. **Run development server**:

   ```bash
   npm run dev
   ```

5. **Open browser**:

   http://localhost:3000

## Project Structure

```
haggler/
├── server/              # Python bot server
│   ├── bot.py           # Main bot implementation
│   ├── pyproject.toml   # Python dependencies
│   ├── .env.example      # Environment variables template
│   ├── .env              # Your API keys (git-ignored)
│   └── ...
├── client/              # React application
│   ├── src/             # Client source code
│   ├── package.json     # Node dependencies
│   └── ...
├── .gitignore           # Git ignore patterns
└── README.md            # This file
```
## Learn More

- [Pipecat Documentation](https://docs.pipecat.ai/)
- [Voice UI Kit Documentation](https://voiceuikit.pipecat.ai/)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
- [Pipecat Examples](https://github.com/pipecat-ai/pipecat-examples)
- [Discord Community](https://discord.gg/pipecat)