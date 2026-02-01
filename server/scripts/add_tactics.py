#!/usr/bin/env python3
"""Add new tactics to agent:tactics (base list). Deduplicates: only appends tactics not already present.

Usage (from server/):
  uv run python scripts/add_tactics.py "Tactic one." "Tactic two."
  uv run python scripts/add_tactics.py --file tactics.txt
  echo "One tactic" | uv run python scripts/add_tactics.py
"""
import argparse
import os
import sys
from pathlib import Path

import redis
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REDIS_TACTICS_KEY = "agent:tactics"


def _decode(b: bytes | str) -> str:
    return b.decode() if isinstance(b, bytes) else b


def main() -> None:
    parser = argparse.ArgumentParser(description="Add tactics to agent:tactics")
    parser.add_argument("tactics", nargs="*", help="Tactic strings to add")
    parser.add_argument("--file", "-f", type=Path, help="Read tactics from file (one per line)")
    args = parser.parse_args()

    tactics_to_add: list[str] = []
    if args.tactics:
        tactics_to_add.extend(args.tactics)
    if args.file:
        tactics_to_add.extend(args.file.read_text().strip().splitlines())
    if not tactics_to_add and not sys.stdin.isatty():
        tactics_to_add.extend(line.strip() for line in sys.stdin if line.strip())

    tactics_to_add = [t.strip() for t in tactics_to_add if t.strip()]
    if not tactics_to_add:
        print("No tactics to add. Pass args, --file path, or stdin.")
        sys.exit(1)

    url = os.getenv("REDIS_URL")
    if not url:
        print("REDIS_URL not set in .env")
        sys.exit(1)

    r = redis.from_url(url)
    existing_raw = r.lrange(REDIS_TACTICS_KEY, 0, -1) or []
    existing = {_decode(x) for x in existing_raw}
    new_only = [t for t in tactics_to_add if t not in existing]
    for t in new_only:
        r.rpush(REDIS_TACTICS_KEY, t)
        existing.add(t)
    r.close()

    if not new_only:
        print("All given tactics already in agent:tactics. Nothing added.")
        return
    print(f"Added {len(new_only)} tactic(s) to agent:tactics:")
    for t in new_only:
        print(f"  - {t[:80]}{'...' if len(t) > 80 else ''}")


if __name__ == "__main__":
    main()
