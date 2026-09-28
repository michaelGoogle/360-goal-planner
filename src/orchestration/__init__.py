"""One function per public endpoint.

An orchestrator sequences services and does no arithmetic of its own. It raises
``GpError`` rather than an ``HTTPException``, so FastAPI stays in ``src.app`` and
these functions can be called from a test or a script.

Today they still call the existing pipeline functions directly; WP4 to WP11 swap
those calls for service clients one at a time, which is why the endpoint bodies
moved here before any logic changed.
"""

from __future__ import annotations

from src.orchestration.needs import run_needs
from src.orchestration.predict import run_predict
from src.orchestration.project import run_project
from src.orchestration.score import run_score

__all__ = ["run_predict", "run_needs", "run_score", "run_project"]
