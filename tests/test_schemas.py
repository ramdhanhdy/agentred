"""Tests for schemas and budget parsing."""

import pytest
from agentred.collect.base import parse_budget, make_job_id
from agentred.schemas import BudgetType, JobPost, Source, DemandSignal, Opportunity


class TestBudgetParsing:
    def test_fixed_price(self):
        bt, lo, hi, raw = parse_budget("$300.00 Fixed Price")
        assert bt == BudgetType.FIXED
        assert lo == 300.0
        assert hi == 300.0

    def test_hourly_range(self):
        bt, lo, hi, raw = parse_budget("$60-$70/hr Hourly")
        assert bt == BudgetType.HOURLY
        assert lo == 60.0
        assert hi == 70.0

    def test_single_hourly(self):
        bt, lo, hi, raw = parse_budget("$50/hr")
        assert bt == BudgetType.HOURLY
        assert lo == 50.0

    def test_empty(self):
        bt, lo, hi, raw = parse_budget("")
        assert bt == BudgetType.UNKNOWN
        assert lo is None

    def test_comma_in_amount(self):
        bt, lo, hi, raw = parse_budget("$1,500 Fixed Price")
        assert bt == BudgetType.FIXED
        assert lo == 1500.0


class TestJobPost:
    def test_to_map_input(self):
        post = JobPost(
            job_id="abc123",
            title="Python Developer",
            url="https://example.com/job/123",
            source=Source.UPWORK,
            description="Need a Python dev for API work",
            skills=["Python", "FastAPI"],
        )
        data = post.to_map_input()
        assert data["title"] == "Python Developer"
        assert data["source"] == "upwork"
        assert "Python" in data["skills"]
        assert len(data["description"]) <= 2000


class TestMakeJobId:
    def test_deterministic(self):
        id1 = make_job_id("upwork", "~012345")
        id2 = make_job_id("upwork", "~012345")
        assert id1 == id2

    def test_different_sources(self):
        id1 = make_job_id("upwork", "~012345")
        id2 = make_job_id("fiverr", "~012345")
        assert id1 != id2


class TestDemandSignal:
    def test_defaults(self):
        sig = DemandSignal(
            signal_id="sig1",
            skill_or_tool="Python",
        )
        assert sig.mention_count == 1
        assert sig.automation_potential == 0.0
        assert sig.confidence == 0.5


class TestOpportunity:
    def test_creation(self):
        opp = Opportunity(
            rank=1,
            title="n8n workflow marketplace",
            what_to_build="A template marketplace for n8n workflows",
            demand_score=85.0,
            evidence=["https://upwork.com/job/1"],
            skill_signals=["n8n", "Zapier"],
            automation_potential=0.8,
            source_count=5,
        )
        assert opp.rank == 1
        assert opp.demand_score == 85.0
        assert opp.competition_level == "unknown"
