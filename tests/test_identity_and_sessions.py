"""A3 (identity stripping and injection) and D1 (session lock)."""
import asyncio

import pytest

from conftest import SESSION, app_module, ps


class FakeToolRequest:
    """The parts of an MCP tool-call request that the interceptor reads and overrides."""

    def __init__(self, name, args, headers=None):
        self.name = name
        self.args = args
        self.headers = headers or {}

    def override(self, args=None, headers=None):
        return FakeToolRequest(self.name, args, headers)


def run_interceptor(model_args, session_id="real-session", user_id="real-user"):
    """Send one tool call through the interceptor and return what reaches the tool."""
    async def handler(request):
        return request

    async def call():
        app_module.current_session_id_var.set(session_id)
        app_module.current_user_id_var.set(user_id)
        return await app_module.SessionIdInjectorInterceptor()(FakeToolRequest("prove_my_data", model_args), handler)

    return asyncio.run(call())


@pytest.mark.parametrize("cfg", ["B", "C", "D"])
def test_interceptor_strips_model_identity_and_injects_session_identity(config, cfg):
    config(cfg)
    sent = run_interceptor({"user_id": "user123", "session_id": "abc123", "proof_type": "KS"})
    assert "user_id" not in sent.args                      # the model's invented identity is dropped
    assert sent.headers["x-user-id"] == "real-user"        # the server injects the real one
    assert sent.args["session_id"] == "real-session"       # an invented session id is replaced
    assert sent.headers["x-session-id"] == "real-session"
    assert sent.args["proof_type"] == "KS"                  # other arguments pass through unchanged


@pytest.mark.parametrize("cfg", ["A", "A_STAR"])
def test_configs_without_a3_let_the_model_identity_through(config, cfg):
    config(cfg)
    sent = run_interceptor({"user_id": "user123"})
    assert sent.args["user_id"] == "user123"
    assert "x-user-id" not in sent.headers
    assert sent.args["session_id"] == "real-session"       # the session id is still injected


@pytest.mark.parametrize("cfg, trusted", [("A", True), ("A_STAR", True), ("B", False), ("C", False), ("D", False)])
def test_prover_server_trusts_a_tool_argument_identity_only_without_a3(config, cfg, trusted):
    config(cfg)
    resolved = ps._resolve_user_id("user123", ctx=None)
    assert resolved == ("user123" if trusted else None)


def test_session_is_locked_to_its_first_user(cm):
    assert cm.claim_or_verify_session_owner(SESSION, "alice") == (True, None)
    assert cm.claim_or_verify_session_owner(SESSION, "alice") == (True, None)
    assert cm.claim_or_verify_session_owner(SESSION, "bob") == (False, "mismatch")


def test_session_lock_fails_closed_when_redis_is_down(cm):
    cm.redis_client = None
    assert cm.claim_or_verify_session_owner(SESSION, "alice") == (False, "redis_down")


def test_chat_endpoint_rejects_another_users_session(cm, monkeypatch):
    monkeypatch.setattr(app_module, "agent", object())  # the agent is never reached
    client = app_module.app.test_client()
    cm.claim_or_verify_session_owner(SESSION, "alice-id")
    with client.session_transaction() as s:
        s["user_id"], s["username"] = "bob-id", "Bob"
    reply = client.post("/get", json={"msg": "check my status", "session_id": SESSION})
    assert reply.status_code == 403
    assert "belongs to another user" in reply.get_data(as_text=True)
