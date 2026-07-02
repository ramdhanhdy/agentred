"""Collection layer for job post aggregation."""

from agentred.collect.base import BaseCollector
from agentred.collect.exa import ExaCollector
from agentred.collect.himalayas import HimalayasCollector
from agentred.collect.jobicy import JobicyCollector

__all__ = [
    "BaseCollector",
    "ExaCollector",
    "HimalayasCollector",
    "JobicyCollector",
]
