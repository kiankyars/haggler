# haggler

A Pipecat AI voice agent built with a realtime speech-to-speech pipeline.

## Configuration

- **Bot Type**: Web
- **Transport(s)**: SmallWebRTC
- **Pipeline**: Realtime
  - **Service**: Gemini Live
- **Modes**: `HAGGLER_MODE=refund` (default) or `negotiation` — refund agent (seeking refund) or negotiation agent (discount/booking/deal). You play the counterparty (support/other side); the agent “calls” you via the client.
- **Weave**: Session config traced at start; session end (config + duration) logged on disconnect. If you get "permission denied" from Weave, create the project in W&B UI (e.g. `kyars/haggler`) or unset `WANDB_API_KEY` to run without tracing.
- **Redis**: `agent:tactics` = tactics list; `agent:winning_tactics` = tactics that won (prepended on next run). Pre-seed via redis-cli: `LPUSH agent:tactics "your tactic"`. Self-improvement: after each call, the bot auto-evaluates the transcript and merges tactics into `agent:winning_tactics` on success.

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

5. **Outcome & self-improvement**: After each call, the bot auto-evaluates the transcript (LLM: did the customer get what they wanted?) and merges tactics into `agent:winning_tactics` on success.

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