"""Shared fixtures for the unit tests of the skeptical checks.

The tests need no network, no LLM, no CoSMeTIC and no Docker:
- Redis is replaced by an in-memory fakeredis instance.
- Calls to the CoSMeTIC provers (curl subprocesses) are replaced by a fake prover.
- CONFIG is read once at import time by app.py and proverserver.py, so tests set the
  module-level SYSTEM_CONFIG directly instead of the environment variable.
- app.py starts a background thread at import that connects to the MCP server; it is
  not started during the tests.
No runtime code is changed for testing.
"""
import json
import os
import subprocess
import sys
import threading

import fakeredis
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Point the global ContextManager at a closed port so its startup ping fails fast;
# each test then gets a fresh fakeredis client (see the `redis` fixture).
os.environ.setdefault("REDIS_HOST", "127.0.0.1")
os.environ.setdefault("REDIS_PORT", "1")

import context_manager as cm_module  # noqa: E402
import proverserver as ps  # noqa: E402

# Import app.py without starting its agent-initialisation thread.
_real_start = threading.Thread.start
threading.Thread.start = lambda self: None
try:
    import app as app_module  # noqa: E402
finally:
    threading.Thread.start = _real_start


SESSION = "test-session"
PORT_OF = {"logistic_accuracy": "5012", "KS": "5013", "LRT": "5014"}


@pytest.fixture
def redis():
    """Give the shared context_manager a fresh in-memory Redis for each test."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    cm_module.context_manager.redis_client = fake
    yield fake
    cm_module.context_manager.redis_client = None


@pytest.fixture
def cm(redis):
    return cm_module.context_manager


@pytest.fixture
def config(monkeypatch):
    """Set the ablation configuration for proverserver.py and app.py."""
    def _set(name):
        monkeypatch.setattr(ps, "SYSTEM_CONFIG", name)
        monkeypatch.setattr(app_module, "SYSTEM_CONFIG", name)
    return _set


class FakeProver:
    """Stands in for the three CoSMeTIC prover APIs reached through curl.

    `jobs` maps a port ("5012", "5013", "5014") to the set of job ids that prover knows.
    Every request URL is recorded in `calls`.
    """

    def __init__(self):
        self.jobs = {"5012": set(), "5013": set(), "5014": set()}
        self.calls = []
        self.download_body = b"PK\x03\x04 fake zip with proof files"

    @staticmethod
    def _port(url):
        return url.split("://", 1)[1].split("/", 1)[0].rsplit(":", 1)[1]

    @staticmethod
    def _job_id(url, marker):
        return url.split(marker, 1)[1].split("/", 1)[0]

    def run_curl(self, url, extra_args="", json_data=None):
        self.calls.append(url)
        port = self._port(url)
        if "/verify-job/" in url:
            job = self._job_id(url, "/verify-job/")
            body = {"ok": True, "results": [], "user_hash": "h"} if job in self.jobs[port] else None
        else:
            job = self._job_id(url, "/jobs/")
            body = {"job_id": job, "status": "done"} if job in self.jobs[port] else None
        if body is None:  # what Flask returns for an unknown job id: an HTML 404 page
            stdout = "<!doctype html><title>404 Not Found</title><p>Unknown job id</p>"
        else:
            stdout = json.dumps(body)
        return subprocess.CompletedProcess(["curl", url], 0, stdout, "")

    def run_download(self, cmd, stdout=None, stderr=None, text=None):
        """Replacement for subprocess.run(["curl", "-L", ..., "-o", path, url])."""
        url = cmd[-1]
        self.calls.append(url)
        path = cmd[cmd.index("-o") + 1]
        with open(path, "wb") as f:
            f.write(self.download_body)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def ports_called(self):
        return [self._port(u) for u in self.calls]


@pytest.fixture
def prover(monkeypatch, tmp_path):
    fake = FakeProver()
    monkeypatch.setattr(ps, "_run_curl_command", fake.run_curl)
    monkeypatch.setattr(ps.subprocess, "run", fake.run_download)
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "downloads"))
    return fake
