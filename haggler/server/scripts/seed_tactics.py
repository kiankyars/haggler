# Run from server/: uv run python scripts/seed_tactics.py
# Requires REDIS_URL in .env (same URL as bot).

import os
import redis

from dotenv import load_dotenv

# Load server/.env when run as uv run python scripts/seed_tactics.py (cwd = server)
load_dotenv(".env")

REDIS_TACTICS_KEY = "agent:tactics"

DEFAULT_TACTICS = [
    "Mention long-term loyalty (e.g. I have been a loyal customer for 10 years).",
    "Ask to speak to a supervisor or retention team if the first agent refuses.",
    "Stay calm and factual; cite policy or precedent if you know it.",
    "Request a partial gesture (e.g. credit or voucher) if full refund is denied.",
    "If they say no, ask what they can do rather than demanding a specific outcome.",
]


def main() -> None:
    url = os.getenv("REDIS_URL")
    if not url:
        print("REDIS_URL not set. Set it in .env or environment.")
        raise SystemExit(1)
    r = redis.from_url(url)
    r.delete(REDIS_TACTICS_KEY)
    r.rpush(REDIS_TACTICS_KEY, *DEFAULT_TACTICS)
    r.close()
    print(f"Seeded {len(DEFAULT_TACTICS)} tactics to {REDIS_TACTICS_KEY}")


if __name__ == "__main__":
    main()
