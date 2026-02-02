#!/usr/bin/env python3
"""Query Redis to show improvement-loop state: tactics, winning_tactics, failed_tactics.

Deduplicates winning_tactics and failed_tactics by cosine similarity on every run.
Run from server/: uv run python scripts/check_redis_improvement.py
"""
import os
import sys
from pathlib import Path

import redis
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tactic_vectors import dedupe_list_by_similarity

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REDIS_TACTICS_KEY = "agent:tactics"
REDIS_WINNING_KEY = "agent:winning_tactics"
REDIS_FAILED_KEY = "agent:failed_tactics"
REDIS_SESSION_PREFIX = "session:"
REDIS_SESSION_SUFFIX = ":tactics"


def _decode(b: bytes | str) -> str:
    return b.decode() if isinstance(b, bytes) else b


def _drop_base_tactics_from_failed(r: redis.Redis) -> int:
    """Remove any agent:tactics entries from agent:failed_tactics. Return count removed."""
    base_raw = r.lrange(REDIS_TACTICS_KEY, 0, -1) or []
    base_set = {_decode(x) for x in base_raw}
    failed_raw = r.lrange(REDIS_FAILED_KEY, 0, -1) or []
    failed = [_decode(x) for x in failed_raw]
    kept = [t for t in failed if t not in base_set]
    removed = len(failed) - len(kept)
    if removed:
        r.delete(REDIS_FAILED_KEY)
        r.delete(REDIS_FAILED_KEY + ":vecs")
        if kept:
            r.rpush(REDIS_FAILED_KEY, *kept)
    return removed


def main() -> None:
    url = os.getenv("REDIS_URL")
    if not url:
        print("REDIS_URL not set in .env")
        return
    url = url.strip()
    if not url.startswith(("redis://", "rediss://", "unix://")):
        url = "redis://" + url
    r = redis.from_url(url)

    # Vector dedupe (cosine similarity); drop base tactics from failed
    n_winning = dedupe_list_by_similarity(r, REDIS_WINNING_KEY)
    n_failed = dedupe_list_by_similarity(r, REDIS_FAILED_KEY)
    n_dropped_base = _drop_base_tactics_from_failed(r)
    if n_winning or n_failed or n_dropped_base:
        print(f"(Deduped by similarity: {n_winning} from winning_tactics, {n_failed} from failed_tactics; {n_dropped_base} base tactics removed from failed_tactics)\n")

    print("=== Improvement loop state (Redis) ===\n")

    # agent:tactics (base tactics list)
    raw = r.lrange(REDIS_TACTICS_KEY, 0, -1)
    tactics = [_decode(x) for x in (raw or [])]

    # agent:winning_tactics (tactics that succeeded)
    raw = r.lrange(REDIS_WINNING_KEY, 0, -1)
    winning = [_decode(x) for x in (raw or [])]
    print(f"agent:winning_tactics ({len(winning)} items)")
    for i, t in enumerate(winning, 1):
        print(f"  {i}. {t[:80]}{'...' if len(t) > 80 else ''}")
    print()

    # agent:failed_tactics (tactics from failed sessions)
    raw = r.lrange(REDIS_FAILED_KEY, 0, -1)
    failed = [_decode(x) for x in (raw or [])]
    print(f"agent:failed_tactics ({len(failed)} items)")
    for i, t in enumerate(failed, 1):
        print(f"  {i}. {t[:80]}{'...' if len(t) > 80 else ''}")
    print()

    r.close()
    print("(Bot uses: winning_tactics first, then tactics; failed_tactics are recorded for evals.)")

if __name__ == "__main__":
    main()
