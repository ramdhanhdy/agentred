"""Tests for the report generator."""

import pytest
from datetime import datetime, timezone
from agentred.report import generate_markdown
from agentred.schemas import (
    DemandSignal, JobPost, MapResult, Opportunity,
    ReduceResult, RunReport, Source,
)


def make_test_report() -> RunReport:
    signals = [
        DemandSignal(
            signal_id="sig1",
            skill_or_tool="Python",
            mention_count=5,
            category="api-integration",
            automation_potential=0.3,
        ),
        DemandSignal(
            signal_id="sig2",
            skill_or_tool="n8n",
            mention_count=3,
            category="automation",
            automation_potential=0.8,
        ),
    ]

    map_result = MapResult(
        batch_id="batch-001",
        demand_signals=signals,
        posts_processed=10,
    )

    opportunities = [
        Opportunity(
            rank=1,
            title="n8n workflow marketplace",
            what_to_build="A template marketplace for n8n workflows targeting real estate",
            demand_score=82.0,
            evidence=["https://upwork.com/job/1", "https://upwork.com/job/2"],
            skill_signals=["n8n", "Zapier"],
            automation_potential=0.85,
            estimated_budget_range="$200-$500",
            competition_level="low",
            why_now="n8n demand up 125% on Fiverr",
            source_count=5,
        ),
    ]

    reduce_result = ReduceResult(
        opportunities=opportunities,
        skill_frequency={"Python": 5, "n8n": 3},
        category_distribution={"api-integration": 1, "automation": 1},
        total_posts_analyzed=10,
        total_signals_extracted=2,
        contradictions=[],
        confidence_notes="High confidence - multiple sources agree",
    )

    return RunReport(
        run_id="test-run-001",
        sources_used=["upwork", "himalayas"],
        total_posts_collected=10,
        total_posts_after_dedup=10,
        map_results=[map_result],
        reduce_result=reduce_result,
        wall_clock_seconds=42.5,
    )


class TestMarkdownReport:
    def test_generates_content(self):
        report = make_test_report()
        md = generate_markdown(report)
        assert "AgentRed Demand Intelligence Report" in md
        assert "n8n workflow marketplace" in md
        assert "test-run-001" in md
        assert "Python" in md

    def test_empty_report(self):
        report = RunReport(
            run_id="empty-001",
            sources_used=[],
            total_posts_collected=0,
            total_posts_after_dedup=0,
            map_results=[],
            reduce_result=None,
        )
        md = generate_markdown(report)
        assert "No opportunities" in md or "0" in md

    def test_contains_skill_table(self):
        report = make_test_report()
        md = generate_markdown(report)
        assert "Skill Frequency" in md
        assert "| Python | 5 |" in md

    def test_contains_evidence_links(self):
        report = make_test_report()
        md = generate_markdown(report)
        assert "https://upwork.com/job/1" in md
