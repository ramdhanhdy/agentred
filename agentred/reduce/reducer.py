"""Reducer agent: merges all mapper results into ranked opportunities.

Takes all MapResult objects, clusters similar signals, resolves
contradictions, and produces a ranked list of build opportunities.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Optional

from agentred.schemas import DemandSignal, MapResult, Opportunity, ReduceResult

REDUCER_SYSTEM_PROMPT = """You are a demand intelligence reducer agent. Your job is to synthesize the output of multiple mapper agents into a ranked list of build opportunities.

You receive demand signals from multiple mappers that analyzed different batches of job postings. Your job is to:

1. AGGREGATE: Merge similar signals. If mapper A found "Python" (3 mentions) and mapper B found "Python" (5 mentions), combine to 8 mentions.

2. CLUSTER: Group related signals into opportunity themes. "n8n", "Zapier", "Make.com" might cluster into "workflow automation platform demand".

3. RANK: Score each opportunity by:
   - Demand volume (total mentions across all posts)
   - Budget signal (are clients paying well?)
   - Automation potential (how much of the work is automatable?)
   - Evidence quality (how many independent sources?)

4. IDENTIFY GAPS: Note any contradictions or missing data between mappers.

Return your analysis as JSON matching this schema:

```json
{
  "opportunities": [
    {
      "rank": 1,
      "title": "string - short name for this opportunity",
      "what_to_build": "string - specific product/tool description",
      "demand_score": 0.0,
      "evidence": ["url1", "url2"],
      "skill_signals": ["skill1", "skill2"],
      "automation_potential": 0.0,
      "estimated_budget_range": "string",
      "competition_level": "low|medium|high",
      "why_now": "string - what makes this timely",
      "source_count": 0
    }
  ],
  "skill_frequency": {"skill_name": count, ...},
  "category_distribution": {"category_name": count, ...},
  "contradictions": ["string - any conflicts between mapper outputs"],
  "confidence_notes": "string - overall assessment of data quality"
}
```

Ranking rules:
- demand_score is 0-100, weighted by mentions, budget, and automation potential
- Top 10 opportunities maximum
- Only include opportunities with at least 2 independent source posts
- "what_to_build" should be specific: "n8n workflow template marketplace for real estate lead gen" not "automation tool"
"""


def build_reducer_prompt(
    map_results: list[MapResult], total_posts: int
) -> str:
    """Build the user prompt for the reducer agent.

    Args:
        map_results: All map results from all mapper waves.
        total_posts: Total number of posts analyzed.

    Returns:
        Formatted prompt string.
    """
    all_signals = []
    for result in map_results:
        for signal in result.demand_signals:
            all_signals.append(
                {
                    "skill_or_tool": signal.skill_or_tool,
                    "mention_count": signal.mention_count,
                    "job_ids": signal.job_ids,
                    "context": signal.context,
                    "budget_signal": signal.budget_signal,
                    "automation_potential": signal.automation_potential,
                    "pain_point": signal.pain_point,
                    "category": signal.category,
                    "confidence": signal.confidence,
                    "batch_id": result.batch_id,
                }
            )

    signals_json = json.dumps(all_signals, indent=2)

    return f"""Synthesize the following demand signals from {len(map_results)} mapper agents that analyzed {total_posts} job postings.

Total signals extracted: {len(all_signals)}

Signals:
```json
{signals_json}
```

Cluster, rank, and return the top build opportunities. Return only valid JSON."""


def deterministic_aggregate(
    map_results: list[MapResult],
) -> tuple[dict[str, int], dict[str, int], list[DemandSignal]]:
    """Deterministically aggregate signals before LLM reduction.

    This does the mechanical merging (dedup, sum counts) so the LLM
    reducer can focus on clustering and ranking.

    Returns:
        Tuple of (skill_frequency, category_distribution, merged_signals).
    """
    # Merge by skill_or_tool (case-insensitive)
    merged: dict[str, DemandSignal] = {}
    skill_freq: Counter = Counter()
    cat_dist: Counter = Counter()

    for result in map_results:
        for signal in result.demand_signals:
            key = signal.skill_or_tool.lower().strip()
            skill_freq[signal.skill_or_tool] += signal.mention_count
            cat_dist[signal.category] += 1

            if key in merged:
                existing = merged[key]
                existing.mention_count += signal.mention_count
                existing.job_ids.extend(signal.job_ids)
                # Keep higher automation potential
                if signal.automation_potential > existing.automation_potential:
                    existing.automation_potential = signal.automation_potential
                # Keep higher confidence
                if signal.confidence > existing.confidence:
                    existing.confidence = signal.confidence
                # Append context
                if signal.context and signal.context not in existing.context:
                    existing.context = f"{existing.context}; {signal.context}"
                if signal.pain_point and signal.pain_point not in existing.pain_point:
                    existing.pain_point = f"{existing.pain_point}; {signal.pain_point}"
            else:
                merged[key] = signal.model_copy(deep=True)

    return dict(skill_freq), dict(cat_dist), list(merged.values())


def parse_reducer_response(
    response_text: str,
    map_results: list[MapResult],
    total_posts: int,
) -> ReduceResult:
    """Parse the reducer agent's response into a ReduceResult.

    Args:
        response_text: Raw text response from the LLM.
        map_results: Original map results for fallback aggregation.
        total_posts: Total posts analyzed.

    Returns:
        ReduceResult with ranked opportunities.
    """
    # Strip markdown code fences
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    # Get deterministic aggregation as fallback
    skill_freq, cat_dist, merged_signals = deterministic_aggregate(map_results)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

    # Parse opportunities
    opportunities = []
    for opp_data in data.get("opportunities", []):
        try:
            opp = Opportunity(
                rank=opp_data.get("rank", len(opportunities) + 1),
                title=opp_data.get("title", ""),
                what_to_build=opp_data.get("what_to_build", ""),
                demand_score=float(opp_data.get("demand_score", 0.0)),
                evidence=opp_data.get("evidence", []),
                skill_signals=opp_data.get("skill_signals", []),
                automation_potential=float(
                    opp_data.get("automation_potential", 0.0)
                ),
                estimated_budget_range=opp_data.get("estimated_budget_range", ""),
                competition_level=opp_data.get("competition_level", "unknown"),
                why_now=opp_data.get("why_now", ""),
                source_count=opp_data.get("source_count", 0),
            )
            opportunities.append(opp)
        except Exception:
            pass

    # Use LLM data if available, fall back to deterministic
    final_skill_freq = data.get("skill_frequency", skill_freq)
    final_cat_dist = data.get("category_distribution", cat_dist)
    contradictions = data.get("contradictions", [])

    return ReduceResult(
        opportunities=opportunities,
        skill_frequency=final_skill_freq,
        category_distribution=final_cat_dist,
        total_posts_analyzed=total_posts,
        total_signals_extracted=sum(
            len(r.demand_signals) for r in map_results
        ),
        contradictions=contradictions,
        confidence_notes=data.get("confidence_notes", ""),
    )
