# haggler

A Pipecat AI voice agent built with a realtime speech-to-speech pipeline.

## Configuration

- **Bot Type**: Web
- **Transport(s)**: SmallWebRTC
- **Pipeline**: Realtime
  - **Service**: Gemini Live
- **Weave**: Session config (system instruction + tactics) traced when `WANDB_API_KEY` is set.
- **Redis**: Optional. Set `REDIS_URL`; tactics stored in list `agent:tactics` are appended to the system instruction. Pre-seed with `uv run python scripts/seed_tactics.py` (from `server/`).

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
│   ├── env.example      # Environment variables template
│   ├── .env             # Your API keys (git-ignored)
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