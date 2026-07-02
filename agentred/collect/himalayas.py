"""Himalayas remote job board collector.

Uses the free Himalayas JSON API (no auth required).
API docs: https://himalayas.app/api
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional

from agentred.collect.base import BaseCollector, make_job_id
from agentred.schemas import JobPost, Source

HIMALAYAS_API = "https://himalayas.app/jobs/api/search"

# Queries that target AI/automation/data roles
DEFAULT_QUERIES = [
    "python",
    "AI agent",
    "automation",
    "LLM",
    "data science",
    "machine learning",
    "API integration",
    "developer",
    "engineer",
    "GPT",
    "OpenAI",
    "Claude",
    "telegram bot",
    "web scraping",
]


class HimalayasCollector(BaseCollector):
    """Collect job posts from Himalayas remote job board."""

    source_name = "himalayas"

    def __init__(
        self,
        queries: list[str] | None = None,
        limit_per_query: int = 100,
    ):
        self.queries = queries or DEFAULT_QUERIES
        self.limit = limit_per_query

    def _search(self, query: str) -> list[dict]:
        """Search Himalayas API for jobs matching query."""
        params = urllib.parse.urlencode({"q": query, "limit": self.limit})
        url = f"{HIMALAYAS_API}?{params}"

        req = urllib.request.Request(
            url, headers={"User-Agent": "AgentRed/0.1"}
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                return data.get("jobs", [])
        except Exception as e:
            print(f"  Himalayas error ('{query}'): {e}", flush=True)
            return []

    def _parse_job(self, job: dict) -> JobPost:
        """Parse a Himalayas job dict into a JobPost."""
        raw_id = str(job.get("id", job.get("slug", "")))
        title = job.get("title", "Untitled")
        url = job.get("url", job.get("apply_url", ""))

        # Build description from available fields
        description_parts = []
        if job.get("description"):
            description_parts.append(job["description"])
        if job.get("responsibilities"):
            description_parts.append(f"Responsibilities: {job['responsibilities']}")
        if job.get("requirements"):
            description_parts.append(f"Requirements: {job['requirements']}")
        description = "\n\n".join(description_parts)[:3000]

        # Skills from tags
        skills = []
        tags = job.get("tags", [])
        if isinstance(tags, list):
            skills = [t.get("name", str(t)) if isinstance(t, dict) else str(t) for t in tags[:10]]

        # Company
        company = ""
        company_data = job.get("company", {})
        if isinstance(company_data, dict):
            company = company_data.get("name", "")
        elif isinstance(company_data, str):
            company = company_data

        # Salary
        salary_min = job.get("salary_min") or job.get("min_salary")
        salary_max = job.get("salary_max") or job.get("max_salary")
        budget = ""
        budget_type_str = "unknown"
        if salary_min and salary_max:
            budget = f"${salary_min}-${salary_max}"
            budget_type_str = "hourly" if job.get("salary_period") == "hourly" else "fixed"

        from agentred.schemas import BudgetType
        budget_type = BudgetType(budget_type_str) if budget_type_str in ("hourly", "fixed") else BudgetType.UNKNOWN

        return JobPost(
            job_id=make_job_id("himalayas", raw_id),
            title=title,
            url=url,
            source=Source.HIMALAYAS,
            description=description,
            company=company,
            skills=skills,
            budget=budget,
            budget_type=budget_type,
            budget_min=float(salary_min) if salary_min else None,
            budget_max=float(salary_max) if salary_max else None,
            category=job.get("category", ""),
        )

    def collect(self, **kwargs) -> list[JobPost]:
        """Collect job posts from Himalayas across all queries."""
        posts: list[JobPost] = []
        seen_ids: set[str] = set()

        print(f"  Collecting from Himalayas ({len(self.queries)} queries)...", flush=True)
        for query in self.queries:
            jobs = self._search(query)
            new = 0
            for job_data in jobs:
                job = self._parse_job(job_data)
                if job.job_id not in seen_ids:
                    seen_ids.add(job.job_id)
                    posts.append(job)
                    new += 1
            print(f"    '{query}': {len(jobs)} results, {new} new", flush=True)

        return posts
