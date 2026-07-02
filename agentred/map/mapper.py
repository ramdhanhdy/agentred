"""Mapper agent: analyzes a batch of job posts and extracts demand signals.

The mapper prompt is designed to be used with any LLM. It takes a batch of
job posts (as JSON), analyzes them, and returns structured demand signals.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Optional

from agentred.schemas import DemandSignal, JobPost, MapResult

MAPPER_SYSTEM_PROMPT = """You are a demand intelligence mapper agent. Your job is to analyze job postings and extract structured demand signals.

For each batch of job posts, you must:

1. IDENTIFY SKILLS AND TOOLS: Extract every technology, skill, tool, or methodology mentioned. Count how many posts mention each.

2. DETECT PAIN POINTS: What problem is the employer trying to solve? What work is currently manual, repetitive, or slow?

3. ASSESS AUTOMATION POTENTIAL: For each skill/tool, rate 0.0-1.0 how automatable the task is with current AI (agents, LLMs, RPA).

4. EXTRACT BUDGET SIGNALS: What are clients willing to pay? Note hourly rates and fixed budgets.

5. CATEGORIZE: Assign each signal to a category: automation, data-engineering, ai-agent-dev, api-integration, web-dev, devops, content, scraping, other.

Return your analysis as JSON matching this schema:

```json
{
  "demand_signals": [
    {
      "skill_or_tool": "string - the technology/skill name",
      "mention_count": 1,
      "job_ids": ["id1", "id2"],
      "context": "string - how it's used in the job posts",
      "budget_signal": "string - pay info if available",
      "automation_potential": 0.0,
      "pain_point": "string - what problem they're solving",
      "category": "string - one of the categories above",
      "confidence": 0.5
    }
  ],
  "processing_notes": "string - observations about this batch"
}
```

Rules:
- Be specific: "n8n" not "automation tool", "LangChain" not "AI framework"
- Extract real pain points: "manual data entry from PDF to CRM" not "data work"
- Automation potential is about the TASK, not the skill
- Confidence: 1.0 = explicitly stated, 0.7 = strongly implied, 0.5 = inferred
- Do NOT invent signals that aren't in the data
- Aggregate: if 3 posts mention "Python", that's one signal with mention_count=3
"""


def build_mapper_prompt(batch: list[JobPost], batch_id: str) -> str:
    """Build the user prompt for a mapper agent.

    Args:
        batch: List of JobPost objects to analyze.
        batch_id: Unique identifier for this batch.

    Returns:
        Formatted prompt string.
    """
    posts_json = json.dumps(
        [post.to_map_input() for post in batch], indent=2
    )

    return f"""Analyze the following {len(batch)} job postings and extract demand signals.

Batch ID: {batch_id}

Job Posts:
```json
{posts_json}
```

Extract all demand signals following the schema. Return only valid JSON."""


def _extract_json_block(text: str) -> str | None:
    """Extract the outermost JSON object from text that may contain prose.

    Uses brace matching to find the first { and its matching }.
    Handles strings with braces inside them (escaped or in quotes).
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape:
            escape = False
            continue

        if ch == "\\":
            escape = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    # No matching closing brace — return everything from start
    # (may be truncated by max_tokens)
    return text[start:]


def parse_mapper_response(
    response_text: str, batch_id: str, posts: list[JobPost]
) -> MapResult:
    """Parse the mapper agent's response into a MapResult.

    Args:
        response_text: Raw text response from the LLM.
        batch_id: The batch ID this result belongs to.
        posts: The original posts (for counting processed).

    Returns:
        MapResult with parsed demand signals.
    """
    # Strip markdown code fences if present
    text = response_text.strip()
    if text.startswith("```"):
        # Remove first line (```json or ```)
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    # Try direct parse first
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # LLM may have wrapped JSON in prose. Extract the JSON block.
        # Strategy: find the outermost { ... } using brace matching
        json_str = _extract_json_block(text)
        if json_str is None:
            return MapResult(
                batch_id=batch_id,
                posts_processed=len(posts),
                errors=["No JSON found in response"],
                processing_notes="Failed to parse mapper response",
            )

        # Repair common LLM JSON mistakes:
        # 1. Trailing commas before } or ]
        repaired = re.sub(r",\s*([}\]])", r"\1", json_str)
        try:
            data = json.loads(repaired)
        except json.JSONDecodeError:
            # 2. Incomplete array (cut off by max_tokens) — try to close it
            signals_match = re.search(
                r'"demand_signals"\s*:\s*\[', repaired
            )
            if signals_match:
                arr_start = signals_match.end()
                last_complete = repaired.rfind("},", arr_start)
                if last_complete > 0:
                    truncated = repaired[: last_complete + 1]
                    truncated += "\n  ]\n}"
                    try:
                        data = json.loads(truncated)
                    except json.JSONDecodeError as e:
                        return MapResult(
                            batch_id=batch_id,
                            posts_processed=len(posts),
                            errors=[f"JSON parse error after repair: {e}"],
                            processing_notes="Failed to parse mapper response",
                        )
                else:
                    return MapResult(
                        batch_id=batch_id,
                        posts_processed=len(posts),
                        errors=["JSON parse error: could not repair truncated response"],
                        processing_notes="Failed to parse mapper response",
                    )
            else:
                return MapResult(
                    batch_id=batch_id,
                    posts_processed=len(posts),
                    errors=["JSON parse error: no demand_signals array found"],
                    processing_notes="Failed to parse mapper response",
                )

    # Parse demand signals
    signals = []
    for sig_data in data.get("demand_signals", []):
        try:
            # Generate signal ID if not provided
            sig_id = sig_data.get("signal_id", "")
            if not sig_id:
                skill = sig_data.get("skill_or_tool", "")
                sig_id = hashlib.sha256(
                    f"{batch_id}:{skill}".encode()
                ).hexdigest()[:16]

            signal = DemandSignal(
                signal_id=sig_id,
                skill_or_tool=sig_data.get("skill_or_tool", ""),
                mention_count=sig_data.get("mention_count", 1),
                job_ids=sig_data.get("job_ids", []),
                context=sig_data.get("context", ""),
                budget_signal=sig_data.get("budget_signal", ""),
                automation_potential=float(
                    sig_data.get("automation_potential", 0.0)
                ),
                pain_point=sig_data.get("pain_point", ""),
                category=sig_data.get("category", ""),
                confidence=float(sig_data.get("confidence", 0.5)),
            )
            signals.append(signal)
        except Exception as e:
            pass  # Skip malformed signals

    return MapResult(
        batch_id=batch_id,
        demand_signals=signals,
        posts_processed=len(posts),
        processing_notes=data.get("processing_notes", ""),
    )
