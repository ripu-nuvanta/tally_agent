"""Fixtures for eval tests.

Eval tests are gated by RUN_EVAL_TESTS=1 environment variable.
They require:
  - Backend running at localhost:8000
  - Frontend running at localhost:5173
  - ANTHROPIC_API_KEY set (for judge phase)
  - Optionally, Tally running for live ground truth
"""

import os
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption("--host", default=os.environ.get("TALLY_HOST", "localhost"))
    parser.addoption("--port", type=int, default=int(os.environ.get("TALLY_PORT", "9000")))
    parser.addoption(
        "--scenario",
        default="all",
        help="Scenario name or 'all' (default: all)",
    )
    parser.addoption(
        "--frontend-url",
        default="http://localhost:5173",
        help="Frontend URL (default: http://localhost:5173)",
    )


@pytest.fixture(scope="session")
def tally_host(request):
    return request.config.getoption("--host")


@pytest.fixture(scope="session")
def tally_port(request):
    return request.config.getoption("--port")


@pytest.fixture(scope="session")
def scenario_name(request):
    return request.config.getoption("--scenario")


@pytest.fixture(scope="session")
def frontend_url(request):
    return request.config.getoption("--frontend-url")


@pytest.fixture(scope="session")
def use_live_ground_truth():
    return bool(os.environ.get("RUN_LIVE_TESTS"))


@pytest.fixture(scope="session")
def eval_results_dir():
    """Ensure results directories exist."""
    base = Path(__file__).parent / "results"
    for subdir in ("transcripts", "screenshots", "scores"):
        (base / subdir).mkdir(parents=True, exist_ok=True)
    return base
