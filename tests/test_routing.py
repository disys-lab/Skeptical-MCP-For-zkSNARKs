"""A1 (proof-type normalization), B4 (job-ID fallback), B5 (stored proof type) and
B6 (prover auto-detection), tested against a fake prover.

These tests document what the code does, including two behaviours that differ from a
simple reading of the paper (see the notes on B5 and B6 below).
"""
import asyncio
import json

import pytest

from conftest import PORT_OF, SESSION, ps


def run(coro):
    return asyncio.run(coro)


# ---------- A1: proof-type normalization ----------

@pytest.mark.parametrize("raw, canonical", [
    ("KS", "KS"), ("ks", "KS"), (" Kolmogorov ", "KS"), ("kolmogorov-smirnov", "KS"), ("kolmogorov_smirnov", "KS"),
    ("LRT", "LRT"), ("lrt", "LRT"), ("likelihood_ratio_test", "LRT"), ("likelihood-ratio-test", "LRT"),
    ("logistic_accuracy", "logistic_accuracy"), ("", "logistic_accuracy"),
])
def test_proof_type_spellings_map_to_canonical_names(raw, canonical):
    assert ps._normalize_proof_type(raw) == canonical


@pytest.mark.xfail(strict=True, reason="Known gap: 'likelihood ratio test' with spaces is not an alias in "
                                       "_normalize_proof_type (only in check_hash_existence), so it falls back "
                                       "to logistic_accuracy.")
def test_spaced_lrt_name_is_normalized():
    assert ps._normalize_proof_type("likelihood ratio test") == "LRT"


@pytest.mark.parametrize("proof_type, port", [("logistic_accuracy", "5012"), ("KS", "5013"), ("LRT", "5014")])
def test_each_proof_type_routes_to_its_own_prover_port(proof_type, port):
    assert ps._get_base_url(proof_type).endswith(":" + port)


# ---------- B4: job-ID fallback ----------

@pytest.mark.parametrize("cfg", ["B", "C", "D"])
def test_missing_job_id_falls_back_to_the_latest_job(cm, prover, config, cfg):
    config(cfg)
    cm.add_job_id(SESSION, "111", "logistic_accuracy", "h")
    prover.jobs["5012"].add("111")
    out = json.loads(run(ps.check_status(session_id=SESSION)))
    assert out["job_id"] == "111" and out["status"] == "done"


def test_config_a_has_no_job_id_fallback(cm, prover, config):
    config("A")
    cm.add_job_id(SESSION, "111", "logistic_accuracy", "h")
    out = json.loads(run(ps.check_status(session_id=SESSION)))
    assert "job_id is required" in out["error"]
    assert prover.calls == []


# ---------- B5: stored proof type in check_status ("complete") ----------

@pytest.mark.parametrize("cfg", ["C", "D"])
def test_check_status_completes_a_missing_proof_type_from_the_stored_job(cm, prover, config, cfg):
    config(cfg)
    cm.add_job_id(SESSION, "222", "KS", "h")
    prover.jobs["5013"].add("222")
    out = json.loads(run(ps.check_status(session_id=SESSION)))
    assert out["status"] == "done"
    assert prover.ports_called() == ["5013"]


def test_config_b_reproduces_the_wrong_port_failure(cm, prover, config):
    """The paper's main failure mode: without B5, an omitted proof type defaults to the
    logistic-accuracy prover, which does not know a KS job and answers with a 404 page."""
    config("B")
    cm.add_job_id(SESSION, "222", "KS", "h")
    prover.jobs["5013"].add("222")
    out = run(ps.check_status(session_id=SESSION))
    assert prover.ports_called() == ["5012"]
    assert out.startswith("Invalid JSON response") and "404" in out


@pytest.mark.parametrize("cfg", ["C", "D"])
def test_check_status_passes_an_explicit_other_proof_type_through(cm, prover, config, cfg):
    config(cfg)
    cm.add_job_id(SESSION, "222", "KS", "h")
    run(ps.check_status(session_id=SESSION, proof_type="LRT"))
    assert prover.ports_called() == ["5014"]   # the model's explicit value is honoured, even if wrong


def test_check_status_cannot_tell_an_explicit_logistic_accuracy_from_the_default(cm, prover, config):
    """'logistic_accuracy' is check_status's default value, so an explicit
    'logistic_accuracy' from the model is treated like an omitted one and completed
    from the stored job."""
    config("C")
    cm.add_job_id(SESSION, "222", "KS", "h")
    prover.jobs["5013"].add("222")
    run(ps.check_status(session_id=SESSION, proof_type="logistic_accuracy"))
    assert prover.ports_called() == ["5013"]


# ---------- B5: stored proof type in download_proof and verify_proof ("override") ----------

def call_tool(tool, **kw):
    if tool == "download_proof":
        return run(ps.download_proof(session_id=SESSION, **kw))
    return run(ps.verify_proof(session_id=SESSION, **kw))


@pytest.mark.parametrize("tool", ["download_proof", "verify_proof"])
@pytest.mark.parametrize("cfg", ["C", "D"])
def test_download_and_verify_override_the_model_proof_type_with_the_stored_one(cm, prover, config, tool, cfg):
    config(cfg)
    cm.add_job_id(SESSION, "333", "KS", "h", status="done")
    prover.jobs["5013"].add("333")
    call_tool(tool, job_id="333", proof_type="LRT")
    assert prover.ports_called() == ["5013"]   # the stored KS wins over the model's LRT


@pytest.mark.parametrize("tool", ["download_proof", "verify_proof"])
def test_config_b_uses_the_model_proof_type(cm, prover, config, tool):
    config("B")
    cm.add_job_id(SESSION, "333", "KS", "h", status="done")
    call_tool(tool, job_id="333", proof_type="LRT")
    assert prover.ports_called() == ["5014"]


@pytest.mark.parametrize("tool", ["download_proof", "verify_proof"])
@pytest.mark.parametrize("cfg", ["A", "B"])
def test_without_a_proof_type_download_and_verify_refuse_to_guess_in_configs_a_and_b(prover, config, tool, cfg):
    config(cfg)
    out = json.loads(call_tool(tool, job_id="444"))
    assert "proof_type is required" in out["error"]
    assert prover.calls == []                  # no prover is contacted


# ---------- B6: prover auto-detection ----------

@pytest.mark.parametrize("tool", ["download_proof", "verify_proof"])
@pytest.mark.parametrize("cfg", ["C", "D"])
@pytest.mark.parametrize("holder", ["logistic_accuracy", "KS", "LRT"])
def test_auto_detection_finds_the_prover_that_holds_the_job(prover, config, tool, cfg, holder):
    config(cfg)
    prover.jobs[PORT_OF[holder]].add("555")
    call_tool(tool, job_id="555")
    probes, final = prover.ports_called()[:3], prover.ports_called()[3]
    assert sorted(probes) == ["5012", "5013", "5014"]
    assert final == PORT_OF[holder]


def test_auto_detection_prefers_lrt_then_ks_when_several_provers_answer(prover, config):
    config("C")
    prover.jobs["5012"].add("666")
    prover.jobs["5013"].add("666")
    call_tool("verify_proof", job_id="666")
    assert prover.ports_called()[-1] == "5013"


def test_auto_detection_falls_back_to_logistic_accuracy_when_no_prover_has_the_job(prover, config):
    """Note: here the tool does guess. The paper (Sec. III-C) says download and verify
    'return an error rather than guessing' when no type is stored; that holds for
    Configs A and B, while Configs C and D probe and then default to logistic accuracy."""
    config("C")
    out = call_tool("verify_proof", job_id="777")
    assert prover.ports_called()[-1] == "5012"
    assert out.startswith("Invalid JSON response") and "404" in out   # the guessed prover does not know the job
