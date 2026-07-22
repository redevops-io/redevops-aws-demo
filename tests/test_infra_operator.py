"""Wiring proof: the real (agentic-os) infra operator drives THIS repo's terraform env.

Uses the operator's injectable runner, so no terraform/AWS is actually invoked ($0). We
assert the exact command it would run points at infra/terraform/envs/aws.
"""
import importlib
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_plan_targets_our_env(infra_core, monkeypatch):
    monkeypatch.setenv("INFRA_DEPLOY_ROOT", str(REPO / "infra"))
    core = importlib.reload(infra_core)  # DEPLOY_ROOT is read at import → reload to pick up env

    calls = []

    def fake_run(argv, cwd=None):
        calls.append(argv)
        return (0, "", "")

    core.terraform_plan("aws", {"region": "us-east-1"}, run=fake_run)
    cmd = " ".join(calls[0])
    assert f"-chdir={REPO}/infra/terraform/envs/aws" in cmd
    assert "plan" in calls[0]
    assert "region=us-east-1" in cmd


def test_destroy_targets_our_env(infra_core, monkeypatch):
    monkeypatch.setenv("INFRA_DEPLOY_ROOT", str(REPO / "infra"))
    core = importlib.reload(infra_core)

    calls = []
    core.terraform_destroy("aws", run=lambda argv, cwd=None: (calls.append(argv) or (0, "", "")))
    cmd = " ".join(calls[0])
    assert f"-chdir={REPO}/infra/terraform/envs/aws" in cmd
    assert "destroy" in calls[0]
