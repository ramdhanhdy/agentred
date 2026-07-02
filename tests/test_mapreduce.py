"""Tests for the partitioner and mapper."""

import pytest
from agentred.map.partitioner import partition, optimal_batch_size
from agentred.map.mapper import build_mapper_prompt, parse_mapper_response
from agentred.schemas import JobPost, Source


def make_posts(n: int) -> list[JobPost]:
    return [
        JobPost(
            job_id=f"job-{i}",
            title=f"Job {i}",
            url=f"https://example.com/job/{i}",
            source=Source.UPWORK,
            description=f"Description for job {i}",
        )
        for i in range(n)
    ]


class TestPartitioner:
    def test_empty(self):
        assert partition([]) == []

    def test_single_batch(self):
        posts = make_posts(10)
        batches = partition(posts, batch_size=50)
        assert len(batches) == 1
        assert len(batches[0]) == 10

    def test_multiple_batches(self):
        posts = make_posts(150)
        batches = partition(posts, batch_size=50)
        assert len(batches) == 3
        assert len(batches[0]) == 50
        assert len(batches[2]) == 50

    def test_shuffle_preserves_all(self):
        posts = make_posts(100)
        batches = partition(posts, batch_size=25)
        all_ids = set()
        for batch in batches:
            for post in batch:
                all_ids.add(post.job_id)
        assert len(all_ids) == 100

    def test_optimal_batch_size(self):
        assert optimal_batch_size(600) <= 100
        assert optimal_batch_size(600) >= 10
        assert optimal_batch_size(0) == 50


class TestMapper:
    def test_build_prompt(self):
        posts = make_posts(3)
        prompt = build_mapper_prompt(posts, "batch-001")
        assert "batch-001" in prompt
        assert "3 job postings" in prompt
        assert "job-0" in prompt

    def test_parse_valid_response(self):
        response = '''
        {
          "demand_signals": [
            {
              "skill_or_tool": "Python",
              "mention_count": 3,
              "job_ids": ["job-0", "job-1", "job-2"],
              "context": "Used for API development",
              "budget_signal": "$50-70/hr",
              "automation_potential": 0.3,
              "pain_point": "Manual API integration",
              "category": "api-integration",
              "confidence": 0.9
            }
          ],
          "processing_notes": "Batch analyzed successfully"
        }
        '''
        posts = make_posts(3)
        result = parse_mapper_response(response, "batch-001", posts)
        assert result.batch_id == "batch-001"
        assert result.posts_processed == 3
        assert len(result.demand_signals) == 1
        assert result.demand_signals[0].skill_or_tool == "Python"
        assert result.demand_signals[0].mention_count == 3

    def test_parse_code_fenced_response(self):
        response = '''```json
        {
          "demand_signals": [],
          "processing_notes": "Empty batch"
        }
        ```
        '''
        posts = make_posts(1)
        result = parse_mapper_response(response, "batch-002", posts)
        assert result.posts_processed == 1
        assert len(result.demand_signals) == 0

    def test_parse_invalid_json(self):
        posts = make_posts(2)
        result = parse_mapper_response("not json at all", "batch-003", posts)
        assert len(result.errors) > 0
        assert result.posts_processed == 2
