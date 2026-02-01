#!/usr/bin/env python3
"""Query Redis to show improvement-loop state: tactics, winning_tactics, failed_tactics.

Deduplicates winning_tactics and failed_tactics automatically on every run.
Run from server/: uv run python scripts/check_redis_improvement.py
"""
import os
import redis
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REDIS_TACTICS_KEY = "agent:tactics"
REDIS_WINNING_KEY = "agent:winning_tactics"
REDIS_FAILED_KEY = "agent:failed_tactics"
REDIS_SESSION_PREFIX = "session:"
REDIS_SESSION_SUFFIX = ":tactics"


def _decode(b: bytes | str) -> str:
    return b.decode() if isinstance(b, bytes) else b


def _dedupe_list(r: redis.Redis, key: str) -> int:
    """Deduplicate list at key (preserve order). Return count removed."""
    raw = r.lrange(key, 0, -1) or []
    decoded = [_decode(x) for x in raw]
    seen = set()
    deduped = []
    for t in decoded:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    removed = len(decoded) - len(deduped)
    if removed:
        r.delete(key)
        if deduped:
            r.rpush(key, *deduped)
    return removed


def main() -> None:
    url = os.getenv("REDIS_URL")
    if not url:
        print("REDIS_URL not set in .env")
        return
    r = redis.from_url(url)

    # Always dedupe on run so Redis lists stay clean
    n_winning = _dedupe_list(r, REDIS_WINNING_KEY)
    n_failed = _dedupe_list(r, REDIS_FAILED_KEY)
    if n_winning or n_failed:
        print(f"(Deduped: {n_winning} from winning_tactics, {n_failed} from failed_tactics)\n")

    print("=== Improvement loop state (Redis) ===\n")

    # agent:tactics (base tactics list)
    raw = r.lrange(REDIS_TACTICS_KEY, 0, -1)
    tactics = [_decode(x) for x in (raw or [])]
    print(f"agent:tactics ({len(tactics)} items)")
    for i, t in enumerate(tactics, 1):
        print(f"  {i}. {t[:80]}{'...' if len(t) > 80 else ''}")
    print()

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

    # Any session:*:tactics still present
    keys = list(r.scan_iter(match=f"{REDIS_SESSION_PREFIX}*{REDIS_SESSION_SUFFIX}"))
    print(f"session:*:tactics keys: {len(keys)}")
    for k in keys[:5]:
        key = _decode(k) if isinstance(k, bytes) else k
        n = r.llen(k)
        print(f"  {key} ({n} tactics)")
    if len(keys) > 5:
        print(f"  ... and {len(keys) - 5} more")
    print()

    r.close()
    print("(Bot uses: winning_tactics first, then tactics; failed_tactics are recorded for evals.)")


if __name__ == "__main__":
    main()
