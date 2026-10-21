"""Post-release fixes: every prover that finds the hash is reported (KS was skipped),
and a login cookie for an account that no longer exists is treated as logged out."""
import asyncio
import json
import subprocess

import pytest

from conftest import app_module, ps

# The real /check-hash/ answers of the three provers for one hash (lab server, Oct 2026).
CHECK_HASH = {
    "5012": {"exists": True, "found_in_both": True, "found_in_log_acc": True, "found_in_log_acc_length": True,
             "hash": "0d", "test_name": "logistic accuracy"},
    "5013": {"exists": True, "found_in_both": False, "found_in_s1": True, "found_in_s2": False,
             "hash": "0d", "test_name": "ks"},
    "5014": {"exists": True, "found_in_both": True, "found_in_ll_full": True, "found_in_ll_reduced": True,
             "hash": "0d", "test_name": "logistic lrt"},
}


def fake_check_hash(answers):
    def run(url, extra_args="", json_data=None):
        port = url.split("://", 1)[1].split("/", 1)[0].rsplit(":", 1)[1]
        return subprocess.CompletedProcess(["curl", url], 0, json.dumps(answers[port]), "")
    return run


def test_every_prover_that_finds_the_hash_gets_its_own_line(monkeypatch):
    monkeypatch.setattr(ps, "_run_curl_command", fake_check_hash(CHECK_HASH))
    out = asyncio.run(ps.check_hash_existence(user_hash="0d"))
    assert "✓ **logistic accuracy**: Hash exists. Details: found in both, found in log_acc, found in log_acc_length" in out
    assert "✓ **KS (Kolmogorov-Smirnov)**: Hash exists. Details: found in s1" in out
    assert "✓ **LRT (Likelihood Ratio Test)**: Hash exists. Details: found in both, found in ll_full, found in ll_reduced" in out
    assert "found in **3 applications**" in out


def test_a_prover_that_finds_the_hash_without_details_is_still_reported(monkeypatch):
    answers = {p: {"exists": True} for p in ("5012", "5013", "5014")}
    monkeypatch.setattr(ps, "_run_curl_command", fake_check_hash(answers))
    out = asyncio.run(ps.check_hash_existence(user_hash="0d", application="KS"))
    assert "✓ **KS (Kolmogorov-Smirnov)**: Hash exists" in out


def test_a_prover_without_the_hash_says_not_found(monkeypatch):
    answers = dict(CHECK_HASH, **{"5013": {"exists": False, "hash": "zz", "test_name": "ks"}})
    monkeypatch.setattr(ps, "_run_curl_command", fake_check_hash(answers))
    out = asyncio.run(ps.check_hash_existence(user_hash="zz", application="KS"))
    assert "✗ **KS (Kolmogorov-Smirnov)**: Hash not found" in out


def me(monkeypatch, lookup):
    monkeypatch.setattr(app_module, "get_user_by_id", lookup)
    client = app_module.app.test_client()
    with client.session_transaction() as s:
        s["user_id"], s["username"] = "old-id", "User1"
    reply = json.loads(client.get("/auth/me").get_data(as_text=True))
    with client.session_transaction() as s:
        left = dict(s)
    return reply, left


def test_a_cookie_for_a_deleted_account_counts_as_logged_out(monkeypatch):
    reply, session_after = me(monkeypatch, lambda uid: None)
    assert reply == {"logged_in": False}
    assert "user_id" not in session_after            # the dead login is cleared


def test_a_cookie_for_an_existing_account_stays_logged_in(monkeypatch):
    reply, _ = me(monkeypatch, lambda uid: {"id": uid, "username": "User1"})
    assert reply == {"logged_in": True, "user": {"id": "old-id", "username": "User1"}}


def test_a_database_outage_does_not_log_the_user_out(monkeypatch):
    def down(uid):
        raise RuntimeError("database unavailable")
    reply, session_after = me(monkeypatch, down)
    assert reply["logged_in"] is True and session_after["user_id"] == "old-id"
