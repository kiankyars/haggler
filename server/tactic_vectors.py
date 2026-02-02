"""Tactic vector store and cosine-similarity deduplication.

Stores tactic embeddings in Redis hashes (list_key:vecs). When adding a tactic,
embeds it and skips if cosine similarity to any existing tactic exceeds threshold.
"""

import json
from typing import Literal

import redis

# Model name for sentence embeddings (local, no API)
EMBED_MODEL = "all-MiniLM-L6-v2"
VECS_SUFFIX = ":vecs"
DEFAULT_SIMILARITY_THRESHOLD = 0.92


def _get_encoder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL)


def embed(tactic: str) -> list[float]:
    """Return sentence embedding for tactic (normalized for cosine sim)."""
    if not tactic.strip():
        return []
    model = _get_encoder()
    vec = model.encode(tactic.strip(), normalize_embeddings=True)
    return vec.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity (assumes vectors are normalized)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _vecs_key(list_key: str) -> str:
    return list_key + VECS_SUFFIX


def _get_cached_vectors(r: redis.Redis, list_key: str, tactics: list[str]) -> dict[str, list[float]]:
    """Return dict tactic -> vector for tactics that have cached vectors."""
    key = _vecs_key(list_key)
    out = {}
    for t in tactics:
        raw = r.hget(key, t)
        if raw:
            out[t] = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
    return out


def _ensure_vector_cached(r: redis.Redis, list_key: str, tactic: str, vec: list[float]) -> None:
    key = _vecs_key(list_key)
    r.hset(key, tactic, json.dumps(vec))


def is_near_duplicate(
    tactic: str,
    existing_tactics: list[str],
    existing_vectors: dict[str, list[float]],
    encoder,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> tuple[bool, list[float]]:
    """Return (True, new_vec) if tactic is near-duplicate of any existing; else (False, new_vec)."""
    if not tactic.strip():
        return True, []
    new_vec = encoder.encode(tactic.strip(), normalize_embeddings=True).tolist()
    for existing in existing_tactics:
        existing_vec = existing_vectors.get(existing)
        if existing_vec is None:
            continue
        if cosine_similarity(new_vec, existing_vec) >= threshold:
            return True, new_vec
    return False, new_vec


def add_tactic_with_dedupe(
    r: redis.Redis,
    list_key: str,
    tactic: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> Literal["added", "duplicate", "skip"]:
    """
    Add tactic to list_key only if no existing tactic has cosine similarity >= threshold.
    Stores embedding in list_key:vecs hash. Returns "added", "duplicate", or "skip" (empty tactic).
    """
    if not tactic.strip():
        return "skip"
    existing_raw = r.lrange(list_key, 0, -1) or []
    existing_tactics = [x.decode() if isinstance(x, bytes) else x for x in existing_raw]
    if tactic in existing_tactics:
        return "duplicate"
    encoder = _get_encoder()
    existing_vectors = _get_cached_vectors(r, list_key, existing_tactics)
    is_dup, new_vec = is_near_duplicate(tactic, existing_tactics, existing_vectors, encoder, threshold)
    if is_dup:
        return "duplicate"
    r.rpush(list_key, tactic)
    _ensure_vector_cached(r, list_key, tactic, new_vec)
    return "added"


def dedupe_list_by_similarity(
    r: redis.Redis,
    list_key: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> int:
    """
    In-place dedupe: keep first of each near-duplicate cluster. Return count removed.
    """
    raw = r.lrange(list_key, 0, -1) or []
    tactics = [x.decode() if isinstance(x, bytes) else x for x in raw]
    if not tactics:
        return 0
    vecs_key = _vecs_key(list_key)
    cached = _get_cached_vectors(r, list_key, tactics)
    encoder = _get_encoder()
    kept = []
    kept_vectors = {}
    for t in tactics:
        vec = cached.get(t)
        if vec is None:
            vec = encoder.encode(t.strip(), normalize_embeddings=True).tolist()
        is_dup, _ = is_near_duplicate(t, kept, kept_vectors, encoder, threshold)
        if not is_dup:
            kept.append(t)
            kept_vectors[t] = vec
    removed = len(tactics) - len(kept)
    if removed:
        r.delete(list_key)
        r.delete(vecs_key)
        if kept:
            r.rpush(list_key, *kept)
            for t, v in kept_vectors.items():
                r.hset(vecs_key, t, json.dumps(v))
    return removed


def _decode(b: bytes | str) -> str:
    return b.decode() if isinstance(b, bytes) else b


def normalize_redis_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url.startswith(("redis://", "rediss://", "unix://")):
        url = "redis://" + url
    return url
