"""Base collector interface and shared utilities."""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from typing import Optional

from agentred.schemas import BudgetType, JobPost


def parse_budget(text: str) -> tuple[BudgetType, Optional[float], Optional[float], str]:
    """Extract budget info from a text string.

    Returns (budget_type, min, max, raw_string).
    """
    if not text:
        return BudgetType.UNKNOWN, None, None, ""

    raw = text.strip()
    lower = raw.lower()

    # Hourly: $50-$70/hr or $50/hr or $50-$70 Hourly
    hourly_match = re.search(
        r"\$(\d[\d,]*\.?\d*)\s*[-\u2013]\s*\$(\d[\d,]*\.?\d*)\s*(?:/hr|hourly|per\s*hour)",
        lower,
    )
    if hourly_match:
        lo = float(hourly_match.group(1).replace(",", ""))
        hi = float(hourly_match.group(2).replace(",", ""))
        return BudgetType.HOURLY, lo, hi, raw

    single_hourly = re.search(r"\$(\d[\d,]*\.?\d*)\s*(?:/hr|hourly|per\s*hour)", lower)
    if single_hourly:
        val = float(single_hourly.group(1).replace(",", ""))
        return BudgetType.HOURLY, val, val, raw

    # Fixed: $300 Fixed Price
    fixed_match = re.search(
        r"\$(\d[\d,]*\.?\d*)\s*(?:fixed|fixed[\s-]?price)", lower
    )
    if fixed_match:
        val = float(fixed_match.group(1).replace(",", ""))
        return BudgetType.FIXED, val, val, raw

    # Bare dollar amount
    bare = re.search(r"\$(\d[\d,]*\.?\d*)", lower)
    if bare:
        val = float(bare.group(1).replace(",", ""))
        return BudgetType.UNKNOWN, val, val, raw

    return BudgetType.UNKNOWN, None, None, raw


def extract_skills(text: str, known_skills: set[str] | None = None) -> list[str]:
    """Extract skills from text using keyword matching.

    Args:
        text: The text to search.
        known_skills: Optional set of lowercase skill names to match.
    """
    if not text or not known_skills:
        return []
    lower = text.lower()
    found = []
    for skill in sorted(known_skills, key=len, reverse=True):
        if skill in lower:
            found.append(skill.title())
    return found[:15]


def make_job_id(source: str, raw_id: str) -> str:
    """Generate a deterministic job ID from source + raw ID."""
    return hashlib.sha256(f"{source}:{raw_id}".encode()).hexdigest()[:16]


class BaseCollector(ABC):
    """Abstract base for all job post collectors."""

    source_name: str = "base"

    @abstractmethod
    def collect(self, **kwargs) -> list[JobPost]:
        """Collect job posts from the source.

        Returns:
            List of JobPost objects.
        """
        ...

    def dedup(self, posts: list[JobPost]) -> list[JobPost]:
        """Remove duplicate posts by job_id."""
        seen = set()
        unique = []
        for post in posts:
            if post.job_id not in seen:
                seen.add(post.job_id)
                unique.append(post)
        return unique
