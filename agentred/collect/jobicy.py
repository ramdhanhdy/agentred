"""Jobicy remote job board collector.

Uses the free Jobicy REST API (no auth required).
API docs: https://jobicy.com/api/v2/remote-jobs
"""

from __future__ import annotations

import json
import urllib.request
from typing import Optional

from agentred.collect.base import BaseCollector, make_job_id
from agentred.schemas import BudgetType, JobPost, Source

JOBICY_API = "https://jobicy.com/api/v2/remote-jobs"


class JobicyCollector(BaseCollector):
    """Collect job posts from Jobicy remote job board."""

    source_name = "jobicy"

    def __init__(self, count: int = 100):
        self.count = min(count, 100)  # API caps at 100

    def _fetch(self) -> list[dict]:
        """Fetch jobs from Jobicy API."""
        url = f"{JOBICY_API}?count={self.count}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "AgentRed/0.1"}
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                return data.get("jobs", [])
        except Exception as e:
            print(f"  Jobicy error: {e}", flush=True)
            return []

    def _parse_job(self, job: dict) -> JobPost | None:
        """Parse a Jobicy job dict into a JobPost."""
        raw_id = str(job.get("id", job.get("jobSlug", "")))
        if not raw_id:
            return None

        title = job.get("jobTitle", job.get("title", "Untitled"))
        url = job.get("url", job.get("jobUrl", ""))

        # Build description
        description = job.get("jobExcerpt", "") or job.get("description", "")
        if job.get("jobDescription"):
            description = f"{description}\n\n{job['jobDescription']}"[:3000]

        # Skills from tags
        skills = []
        tags = job.get("tags", [])
        if isinstance(tags, list):
            skills = [t if isinstance(t, str) else t.get("name", str(t)) for t in tags[:10]]

        # Company
        company = job.get("companyName", job.get("company", ""))

        # Salary
        salary = job.get("salary", "")
        budget_type = BudgetType.UNKNOWN
        budget_min = None
        budget_max = None
        if salary:
            # Jobicy salary format: "$5000 - $7000" or "$50/hr"
            import re
            range_match = re.search(r"\$(\d[\d,]*)\s*-\s*\$(\d[\d,]*)", salary)
            if range_match:
                budget_min = float(range_match.group(1).replace(",", ""))
                budget_max = float(range_match.group(2).replace(",", ""))
                budget_type = BudgetType.FIXED
            else:
                single_match = re.search(r"\$(\d[\d,]*)", salary)
                if single_match:
                    budget_min = float(single_match.group(1).replace(",", ""))
                    budget_max = budget_min
                    budget_type = BudgetType.FIXED

        # Industry as category
        industry = job.get("industry", "")
        if isinstance(industry, list):
            industry = ", ".join(industry[:3])

        return JobPost(
            job_id=make_job_id("jobicy", raw_id),
            title=title,
            url=url,
            source=Source.JOBICY,
            description=description,
            company=company,
            skills=skills,
            budget=salary,
            budget_type=budget_type,
            budget_min=budget_min,
            budget_max=budget_max,
            category=industry,
        )

    def collect(self, **kwargs) -> list[JobPost]:
        """Collect job posts from Jobicy."""
        print(f"  Collecting from Jobicy (count={self.count})...", flush=True)
        jobs = self._fetch()
        posts = []
        for job_data in jobs:
            post = self._parse_job(job_data)
            if post:
                posts.append(post)
        print(f"    Parsed {len(posts)} job posts", flush=True)
        return self.dedup(posts)
