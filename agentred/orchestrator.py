"""Orchestrator: runs the full MapReduce pipeline.

Coordinates collection, partitioning, mapping (in waves), and reduction
into a final report. Designed to work with any LLM backend via a simple
call interface.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from agentred.collect import ExaCollector, HimalayasCollector, JobicyCollector
from agentred.map.mapper import build_mapper_prompt, parse_mapper_response
from agentred.map.partitioner import partition, optimal_batch_size
from agentred.reduce.reducer import build_reducer_prompt, parse_reducer_response
from agentred.schemas import JobPost, MapResult, RunReport


# Type for the LLM call function
LLMCallable = Callable[[str, str], str]
"""Function that takes (system_prompt, user_prompt) and returns response text."""


def collect_all(
    use_exa: bool = True,
    use_himalayas: bool = True,
    use_jobicy: bool = True,
) -> list[JobPost]:
    """Collect job posts from all enabled sources.

    Args:
        use_exa: Whether to use EXA (Upwork + Fiverr).
        use_himalayas: Whether to use Himalayas API.
        use_jobicy: Whether to use Jobicy API.

    Returns:
        Deduplicated list of JobPost objects from all sources.
    """
    posts: list[JobPost] = []

    if use_exa:
        try:
            collector = ExaCollector()
            posts.extend(collector.collect())
        except ValueError as e:
            print(f"  Skipping EXA: {e}", flush=True)

    if use_himalayas:
        collector = HimalayasCollector()
        posts.extend(collector.collect())

    if use_jobicy:
        collector = JobicyCollector()
        posts.extend(collector.collect())

    # Global dedup across sources
    seen: set[str] = set()
    unique: list[JobPost] = []
    for post in posts:
        if post.job_id not in seen:
            seen.add(post.job_id)
            unique.append(post)

    return unique


def run_mapreduce(
    posts: list[JobPost],
    llm_call: LLMCallable,
    batch_size: Optional[int] = None,
    max_concurrent: int = 2,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> tuple[list[MapResult], RunReport]:
    """Run the MapReduce pipeline on collected job posts.

    Args:
        posts: Collected job posts to analyze.
        llm_call: Function that takes (system_prompt, user_prompt) and returns text.
        batch_size: Override automatic batch sizing.
        max_concurrent: Max parallel mappers per wave.
        progress_callback: Optional callback(phase, current, total) for progress updates.

    Returns:
        Tuple of (map_results, run_report).
    """
    start_time = time.time()
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dt%H%M%SZ")

    # Phase 1: Partition
    if batch_size is None:
        batch_size = optimal_batch_size(len(posts), max_concurrent)

    batches = partition(posts, batch_size)
    total_batches = len(batches)

    if progress_callback:
        progress_callback("map", 0, total_batches)

    # Phase 2: Map (sequential waves, respecting concurrency)
    map_results: list[MapResult] = []

    from agentred.map.mapper import MAPPER_SYSTEM_PROMPT

    for i, batch in enumerate(batches):
        batch_id = f"batch-{i+1:03d}"
        prompt = build_mapper_prompt(batch, batch_id)

        if progress_callback:
            progress_callback("map", i + 1, total_batches)

        print(f"  [Map] Batch {i+1}/{total_batches} ({len(batch)} posts)...", flush=True)

        response = llm_call(MAPPER_SYSTEM_PROMPT, prompt)
        result = parse_mapper_response(response, batch_id, batch)
        map_results.append(result)

        print(
            f"    -> {len(result.demand_signals)} signals, "
            f"{result.posts_processed} posts processed",
            flush=True,
        )

    # Phase 3: Reduce
    if progress_callback:
        progress_callback("reduce", 0, 1)

    from agentred.reduce.reducer import REDUCER_SYSTEM_PROMPT

    reducer_prompt = build_reducer_prompt(map_results, len(posts))
    response = llm_call(REDUCER_SYSTEM_PROMPT, reducer_prompt)
    reduce_result = parse_reducer_response(response, map_results, len(posts))

    if progress_callback:
        progress_callback("reduce", 1, 1)

    # Build run report
    report = RunReport(
        run_id=run_id,
        sources_used=list({p.source.value for p in posts}),
        total_posts_collected=len(posts),
        total_posts_after_dedup=len(posts),
        map_results=map_results,
        reduce_result=reduce_result,
        wall_clock_seconds=time.time() - start_time,
    )

    return map_results, report


def save_run_report(report: RunReport, output_dir: str = "output") -> Path:
    """Save the run report as JSON.

    Args:
        report: The RunReport to save.
        output_dir: Directory to save to.

    Returns:
        Path to the saved JSON file.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{report.run_id}.json"
    path.write_text(report.model_dump_json(indent=2))
    return path
