"""Partitioner: splits collected job posts into batches for mapper agents."""

from __future__ import annotations

import math
from agentred.schemas import JobPost


def partition(posts: list[JobPost], batch_size: int = 50) -> list[list[JobPost]]:
    """Split job posts into batches for parallel mapper processing.

    Args:
        posts: List of collected JobPost objects.
        batch_size: Max posts per batch. Default 50.

    Returns:
        List of batches (each a list of JobPost).
    """
    if not posts:
        return []

    # Shuffle to mix sources (Upwork + Fiverr + Himalayas + Jobicy in each batch)
    import random
    shuffled = posts.copy()
    random.seed(42)  # deterministic for reproducibility
    random.shuffle(shuffled)

    batches = []
    for i in range(0, len(shuffled), batch_size):
        batches.append(shuffled[i : i + batch_size])

    return batches


def optimal_batch_size(total_posts: int, max_mappers: int = 2) -> int:
    """Calculate optimal batch size given total posts and mapper concurrency.

    Targets 3-8 batches per wave (enough for good reduce, not too many waves).
    """
    if total_posts <= 0:
        return 50
    # Aim for ~5-7 batches total
    target_batches = 6
    size = math.ceil(total_posts / target_batches)
    # Clamp to reasonable range
    return max(10, min(size, 100))
