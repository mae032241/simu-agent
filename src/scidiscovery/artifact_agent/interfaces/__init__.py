"""Narrow root and scientific-worker interfaces for SciDiscovery."""

from .mcp_root import ROOT_TOOLS, RootMCPRouter, RootToolFacade
from .mcp_worker import WORKER_TOOLS, WorkerMCPRouter

__all__ = [
    "ROOT_TOOLS",
    "RootMCPRouter",
    "RootToolFacade",
    "WORKER_TOOLS",
    "WorkerMCPRouter",
]
