# Run from server/: uv run python scripts/log_outcome.py <session_id> <success|fail>
# Logs outcome to Weave; on success, merges session tactics into agent:winning_tactics (self-improvement).

import os
import sys
import redis

from dotenv import load_dotenv

load_dotenv(".env")

REDIS_TACTICS_KEY = "agent:tactics"
REDIS_WINNING_KEY = "agent:winning_tactics"
REDIS_SESSION_TACTICS_PREFIX = "session:"
REDIS_SESSION_TACTICS_SUFFIX = ":tactics"


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: log_outcome.py <session_id> <success|fail>")
        raise SystemExit(1)
    session_id = sys.argv[1]
    outcome = sys.argv[2].lower()
    if outcome not in ("success", "fail"):
        print("outcome must be success or fail")
        raise SystemExit(1)

    if os.getenv("WANDB_API_KEY"):
        import weave
        weave.init(os.getenv("WEAVE_PROJECT", "haggler"))

        @weave.op()
        def record_outcome(sid: str, result: str) -> None:
            return None

        record_outcome(session_id, outcome)

    url = os.getenv("REDIS_URL")
    if url and outcome == "success":
        r = redis.from_url(url)
        key = f"{REDIS_SESSION_TACTICS_PREFIX}{session_id}{REDIS_SESSION_TACTICS_SUFFIX}"
        raw = r.lrange(key, 0, -1)
        tactics = [b.decode() if isinstance(b, bytes) else b for b in (raw or [])]
        existing = set(r.lrange(REDIS_WINNING_KEY, 0, -1) or [])
        existing_decoded = {e.decode() if isinstance(e, bytes) else e for e in existing}
        for t in tactics:
            if t not in existing_decoded:
                r.rpush(REDIS_WINNING_KEY, t)
                existing_decoded.add(t)
        r.delete(key)
        r.close()
        print(f"Logged outcome={outcome} session_id={session_id}; merged {len(tactics)} tactics into {REDIS_WINNING_KEY}")
    else:
        print(f"Logged outcome={outcome} session_id={session_id}")
    if not os.getenv("WANDB_API_KEY"):
        print("(Set WANDB_API_KEY to log to Weave)")


if __name__ == "__main__":
    main()
