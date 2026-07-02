"""Pydantic models for job posts, demand signals, and opportunities."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class Source(str, Enum):
    UPWORK = "upwork"
    FIVERR = "fiverr"
    HIMALAYAS = "himalayas"
    JOBICY = "jobicy"
    MANUAL = "manual"


class BudgetType(str, Enum):
    FIXED = "fixed"
    HOURLY = "hourly"
    UNKNOWN = "unknown"


class JobPost(BaseModel):
    """A single job posting collected from a source platform."""

    job_id: str = Field(..., description="Unique ID from the source platform")
    title: str
    url: str
    source: Source
    description: str = ""
    company: str = ""
    category: str = ""
    skills: list[str] = Field(default_factory=list)
    budget: str = ""
    budget_type: BudgetType = BudgetType.UNKNOWN
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    experience_level: str = ""
    posted_at: Optional[datetime] = None
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_map_input(self) -> dict:
        """Compact representation for mapper agents."""
        return {
            "job_id": self.job_id,
            "title": self.title,
            "source": self.source.value,
            "url": self.url,
            "description": self.description[:2000],
            "skills": self.skills,
            "budget": self.budget,
            "budget_type": self.budget_type.value,
            "experience_level": self.experience_level,
            "category": self.category,
        }


class DemandSignal(BaseModel):
    """A single demand signal extracted by a mapper from one or more job posts."""

    signal_id: str = Field(..., description="Unique ID for this signal")
    skill_or_tool: str = Field(..., description="The skill, tool, or technology mentioned")
    mention_count: int = Field(default=1, ge=1, description="How many jobs mention this")
    job_ids: list[str] = Field(default_factory=list, description="Source job post IDs")
    context: str = Field("", description="How the skill is used in context")
    budget_signal: str = Field("", description="Budget info associated with this signal")
    automation_potential: float = Field(
        0.0, ge=0.0, le=1.0, description="0=manual, 1=fully automatable"
    )
    pain_point: str = Field("", description="What problem the employer is solving")
    category: str = Field("", description="Functional category: automation, data, dev, etc.")
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class Opportunity(BaseModel):
    """A ranked build opportunity produced by the reducer."""

    rank: int
    title: str
    what_to_build: str
    demand_score: float = Field(..., ge=0.0, le=100.0)
    evidence: list[str] = Field(default_factory=list, description="Job post URLs")
    skill_signals: list[str] = Field(default_factory=list)
    automation_potential: float = Field(0.0, ge=0.0, le=1.0)
    estimated_budget_range: str = ""
    competition_level: str = Field("unknown", description="low, medium, high")
    why_now: str = ""
    source_count: int = 0


class MapResult(BaseModel):
    """Output from one mapper agent processing a batch of job posts."""

    batch_id: str
    mapper_model: str = ""
    demand_signals: list[DemandSignal] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    posts_processed: int = 0
    processing_notes: str = ""


class ReduceResult(BaseModel):
    """Output from the reducer agent synthesizing all map results."""

    opportunities: list[Opportunity] = Field(default_factory=list)
    skill_frequency: dict[str, int] = Field(default_factory=dict)
    category_distribution: dict[str, int] = Field(default_factory=dict)
    total_posts_analyzed: int = 0
    total_signals_extracted: int = 0
    contradictions: list[str] = Field(default_factory=list)
    reducer_model: str = ""
    confidence_notes: str = ""


class RunReport(BaseModel):
    """Full run report: collection + map + reduce + metadata."""

    run_id: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    sources_used: list[str] = Field(default_factory=list)
    total_posts_collected: int = 0
    total_posts_after_dedup: int = 0
    map_results: list[MapResult] = Field(default_factory=list)
    reduce_result: Optional[ReduceResult] = None
    wall_clock_seconds: float = 0.0
