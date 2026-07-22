"""Vault→STS assume-role helper — exercised with a stub Vault + moto (no real cloud, $0).

Covers: correct role→ARN assumption, region wiring, per-role caching, unknown-role
rejection, and the security invariant that key material never leaks into repr/logs.
"""
import logging

import boto3
import pytest

try:  # moto 5
    from moto import mock_aws
except ImportError:  # moto 4 fallback
    from moto import mock_sts as mock_aws  # type: ignore

from aws_demo.creds import AwsDemoCreds

ACCOUNT = "123456789012"
FAKE_VAULT = {
    "secret/redevops/aws-demo/config": {
        "account_id": ACCOUNT,
        "region": "us-east-1",
        "deploy_role_arn": f"arn:aws:iam::{ACCOUNT}:role/redevops-demo-deployer",
        "agent_role_arn": f"arn:aws:iam::{ACCOUNT}:role/redevops-demo-agent",
        "readonly_role_arn": f"arn:aws:iam::{ACCOUNT}:role/redevops-demo-readonly",
    },
    "secret/redevops/aws-demo/bootstrap": {
        "access_key_id": "AKIAEXAMPLEBOOTSTRAP",
        "secret_access_key": "sk-bootstrap-supersecret-should-never-leak",
    },
}


def _reader(path):
    return dict(FAKE_VAULT[path])


@mock_aws
@pytest.mark.parametrize("role", ["deployer", "agent", "readonly"])
def test_session_assumes_the_right_role(role):
    creds = AwsDemoCreds(vault_reader=_reader)
    session = creds.session(role)
    ident = session.client("sts").get_caller_identity()
    assert f"redevops-demo-{role}" in ident["Arn"]
    assert session.region_name == "us-east-1"


@mock_aws
def test_sessions_are_cached_per_role():
    creds = AwsDemoCreds(vault_reader=_reader)
    a = creds.session("deployer")
    b = creds.session("deployer")
    assert a is b  # same short-lived session reused
    assert creds.session("readonly") is not a  # different role, different session


@mock_aws
def test_unknown_role_rejected():
    creds = AwsDemoCreds(vault_reader=_reader)
    with pytest.raises(KeyError):
        creds.session("root")  # type: ignore[arg-type]


@mock_aws
def test_non_secret_config_surface():
    creds = AwsDemoCreds(vault_reader=_reader)
    assert creds.account_id == ACCOUNT
    assert creds.region == "us-east-1"
    assert creds.role_arn("agent").endswith("redevops-demo-agent")


@mock_aws
def test_key_material_never_leaks(caplog):
    """Our object's repr/str never expose key material, and OUR module logs nothing secret.

    (botocore's own DEBUG verbosity is framework behaviour outside this module's control;
    we assert only on records emitted by the ``aws_demo`` logger tree.)
    """
    secret = FAKE_VAULT["secret/redevops/aws-demo/bootstrap"]["secret_access_key"]
    key_id = FAKE_VAULT["secret/redevops/aws-demo/bootstrap"]["access_key_id"]
    creds = AwsDemoCreds(vault_reader=_reader)
    with caplog.at_level(logging.DEBUG):
        creds.session("deployer")
        rendered = f"{creds!r} {creds!s}"

    # our object never renders key material
    assert secret not in rendered and key_id not in rendered
    assert "***redacted***" in rendered

    # our module emits no secret-bearing log records
    ours = [r.getMessage() for r in caplog.records if r.name.startswith("aws_demo")]
    assert all(secret not in m and key_id not in m for m in ours)
