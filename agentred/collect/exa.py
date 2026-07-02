"""EXA-powered collector for Upwork and Fiverr job postings.

Uses the EXA search API (api.exa.ai) to discover job postings on
freelance platforms. Requires EXA_API_KEY environment variable.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Optional

from agentred.collect.base import BaseCollector, make_job_id, parse_budget
from agentred.schemas import BudgetType, JobPost, Source

EXA_SEARCH_URL = "https://api.exa.ai/search"
EXA_CONTENTS_URL = "https://api.exa.ai/contents"

# Default search queries for freelance platforms
DEFAULT_UPWORK_QUERIES = [
    "AI agent automation python freelance",
    "LLM API integration freelance developer",
    "data pipeline scraping python automation",
    "n8n automation workflow integration",
    "telegram bot development python API",
    "RAG chatbot development python",
    "AI evaluation data labeling python",
    "workflow automation API integration python",
]

DEFAULT_FIVERR_QUERIES = [
    "AI agent development automation n8n",
    "Claude Code specialist automation",
    "n8n workflow automation setup",
    "AI chatbot development python LLM",
]

# Common skills to look for in job descriptions
SKILL_KEYWORDS = {
    "python", "javascript", "typescript", "react", "node.js", "fastapi",
    "django", "flask", "docker", "kubernetes", "aws", "azure", "gcp",
    "api", "rest api", "graphql", "openai", "claude", "anthropic", "gpt",
    "llm", "rag", "langchain", "autogen", "crewai", "n8n", "zapier",
    "make.com", "airtable", "supabase", "postgres", "redis", "mongodb",
    "telegram", "discord", "slack", "webhook", "automation", "scraping",
    "data pipeline", "etl", "pandas", "numpy", "machine learning",
    "deep learning", "pytorch", "tensorflow", "huggingface",
    "ai agent", "ai automation", "chatbot", "nlp", "fine-tuning",
    "vector database", "pinecone", "chroma", "embedding",
    "ci/cd", "github actions", "linux", "bash", "terraform",
}


class ExaCollector(BaseCollector):
    """Collect job posts from Upwork and Fiverr via EXA search API."""

    source_name = "exa"

    def __init__(
        self,
        api_key: Optional[str] = None,
        upwork_queries: list[str] | None = None,
        fiverr_queries: list[str] | None = None,
        max_results_per_query: int = 50,
    ):
        self.api_key = api_key or os.environ.get("EXA_API_KEY", "")
        if not self.api_key:
            raise ValueError("EXA_API_KEY not set. Get one at https://exa.ai")

        self.upwork_queries = upwork_queries or DEFAULT_UPWORK_QUERIES
        self.fiverr_queries = fiverr_queries or DEFAULT_FIVERR_QUERIES
        self.max_results = max_results_per_query

    def _search(self, query: str, domain: str) -> list[dict]:
        """Search EXA for job postings on a specific domain."""
        body = json.dumps(
            {
                "query": query,
                "type": "auto",
                "numResults": self.max_results,
                "includeDomains": [domain],
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            EXA_SEARCH_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data.get("results", [])
        except Exception as e:
            print(f"  EXA search error ({domain}, '{query}'): {e}", flush=True)
            return []

    def _parse_upwork_result(self, result: dict) -> JobPost | None:
        """Parse an EXA search result into a JobPost."""
        url = result.get("url", "")
        title = result.get("title", "")
        description = result.get("text", "") or result.get("description", "")

        if "upwork.com/freelance-jobs/apply/" not in url:
            return None

        # Extract job ID from URL
        job_id_match = re.search(r"~[0-9a-f]+", url)
        if not job_id_match:
            return None
        raw_id = job_id_match.group()

        # Clean title
        clean_title = re.sub(r"\s*-\s*Freelance Job.*$", "", title)
        clean_title = re.sub(r"\s*-\s*Upwork$", "", clean_title)

        # Parse budget
        budget_text = f"{title} {description}"
        budget_type, budget_min, budget_max, budget_raw = parse_budget(
            budget_text
        )

        # Extract skills
        skills: list[str] = []
        lower_desc = description.lower()
        for skill in sorted(SKILL_KEYWORDS, key=len, reverse=True):
            if skill in lower_desc and skill.title() not in skills:
                skills.append(skill.title())
        skills = skills[:10]

        # Experience level
        experience = ""
        exp_match = re.search(
            r"(Entry|Intermediate|Expert)\s+(?:Level|Experience)", description
        )
        if exp_match:
            experience = exp_match.group(1)

        return JobPost(
            job_id=make_job_id("upwork", raw_id),
            title=clean_title.strip(),
            url=url,
            source=Source.UPWORK,
            description=description[:3000],
            skills=skills,
            budget=budget_raw,
            budget_type=budget_type,
            budget_min=budget_min,
            budget_max=budget_max,
            experience_level=experience,
        )

    def _parse_fiverr_result(self, result: dict) -> JobPost | None:
        """Parse an EXA search result into a JobPost for Fiverr."""
        url = result.get("url", "")
        title = result.get("title", "")
        description = result.get("text", "") or result.get("description", "")

        if "fiverr.com" not in url:
            return None

        # Use URL hash as ID
        raw_id = url.split("/")[-1].split("?")[0]

        # Extract skills
        skills: list[str] = []
        lower_desc = description.lower()
        for skill in sorted(SKILL_KEYWORDS, key=len, reverse=True):
            if skill in lower_desc and skill.title() not in skills:
                skills.append(skill.title())
        skills = skills[:10]

        return JobPost(
            job_id=make_job_id("fiverr", raw_id),
            title=title.strip(),
            url=url,
            source=Source.FIVERR,
            description=description[:3000],
            skills=skills,
        )

    def collect(self, **kwargs) -> list[JobPost]:
        """Collect job posts from Upwork and Fiverr via EXA."""
        posts: list[JobPost] = []

        # Upwork
        print(f"  Collecting from Upwork ({len(self.upwork_queries)} queries)...", flush=True)
        for query in self.upwork_queries:
            results = self._search(query, "upwork.com")
            for r in results:
                post = self._parse_upwork_result(r)
                if post:
                    posts.append(post)
            print(f"    '{query}': {len(results)} results", flush=True)

        # Fiverr
        print(f"  Collecting from Fiverr ({len(self.fiverr_queries)} queries)...", flush=True)
        for query in self.fiverr_queries:
            results = self._search(query, "fiverr.com")
            for r in results:
                post = self._parse_fiverr_result(r)
                if post:
                    posts.append(post)
            print(f"    '{query}': {len(results)} results", flush=True)

        return self.dedup(posts)
