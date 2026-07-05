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
        """Parse a Himalayas job dict into a JobPost.

        The API response structure changed: the old ``id``/``slug`` fields are
        gone. We use ``guid`` (always present, unique per job) and fall back
        through ``applicationLink`` and a title+company hash for robustness.
        """
        raw_id = str(
            job.get("guid")
            or job.get("applicationLink")
            or job.get("id")
            or job.get("slug")
            or f"{job.get('companyName', '')}_{job.get('title', '')}"
        )
        title = job.get("title", "Untitled")
        url = job.get("applicationLink") or job.get("url") or job.get("apply_url", "")

        # Build description from available fields
        description_parts = []
        if job.get("description"):
            description_parts.append(job["description"])
        if job.get("responsibilities"):
            description_parts.append(f"Responsibilities: {job['responsibilities']}")
        if job.get("requirements"):
            description_parts.append(f"Requirements: {job['requirements']}")
        description = "\n\n".join(description_parts)[:3000]

        # Skills from categories (new API) or tags (old API)
        skills: list[str] = []
        cats = job.get("categories") or job.get("parentCategories")
        if isinstance(cats, list):
            skills = [str(c) for c in cats[:10]]
        else:
            tags = job.get("tags", [])
            if isinstance(tags, list):
                skills = [t.get("name", str(t)) if isinstance(t, dict) else str(t) for t in tags[:10]]

        # Company — new API uses flat "companyName", old API used nested dict
        company = ""
        if job.get("companyName"):
            company = job["companyName"]
        elif isinstance(job.get("company"), dict):
            company = job["company"].get("name", "")
        elif isinstance(job.get("company"), str):
            company = job["company"]

        # Salary — new API uses camelCase, old API used snake_case
        salary_min = job.get("minSalary") or job.get("salary_min") or job.get("min_salary")
        salary_max = job.get("maxSalary") or job.get("salary_max") or job.get("max_salary")
        salary_period = job.get("salaryPeriod") or job.get("salary_period")
        budget = ""
        budget_type_str = "unknown"
        if salary_min and salary_max:
            budget = f"${salary_min}-${salary_max}"
            budget_type_str = "hourly" if salary_period == "hourly" else "fixed"

        from agentred.schemas import BudgetType
        budget_type = BudgetType(budget_type_str) if budget_type_str in ("hourly", "fixed") else BudgetType.UNKNOWN

        # Category — new API uses "parentCategories" list, old used "category" string
        parent_cats = job.get("parentCategories", [])
        category = parent_cats[0] if isinstance(parent_cats, list) and parent_cats else job.get("category", "")

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
            category=category,
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
