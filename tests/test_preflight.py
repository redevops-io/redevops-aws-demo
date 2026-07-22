"""Preflight/doctor — report logic, rendering, local checks, and AWS identity via moto."""
import boto3

try:
    from moto import mock_aws
except ImportError:
    from moto import mock_sts as mock_aws  # type: ignore

from aws_demo.preflight import Check, Report, _CONTAINER_TOOLS, check_aws, check_local, render


def test_ready_and_blockers_logic():
    r = Report()
    r.add(Check("a", "ok"))
    r.add(Check("b", "warn", "optional"))
    assert r.ready and not r.blockers  # warnings don't block
    r.add(Check("c", "fail", "x", "do y"))
    assert not r.ready and len(r.blockers) == 1


def test_render_shows_fixes_for_non_ok():
    r = Report()
    r.add(Check("docker", "fail", "missing", "Install Docker"))
    out = render(r)
    assert "docker" in out and "Install Docker" in out and "BLOCKED" in out


def test_local_checks_cover_docker_and_container_tools():
    r = Report()
    check_local(r)
    names = [c.name for c in r.checks]
    assert "docker" in names
    for t in _CONTAINER_TOOLS:
        assert t in names


@mock_aws
def test_aws_identity_region_and_deployer_probe():
    sess = boto3.Session(region_name="us-east-1")
    r = Report()
    check_aws(r, lambda role: sess)  # solo mode: same ambient session for every role
    by = {c.name: c for c in r.checks}
    assert by["aws-credentials"].status == "ok"
    assert by["region"].status == "ok"
    assert by["perm:deployer(eks)"].status == "ok"  # moto supports eks:ListClusters


@mock_aws
def test_wrong_region_warns_not_blocks():
    sess = boto3.Session(region_name="eu-west-1")
    r = Report()
    check_aws(r, lambda role: sess)
    region = next(c for c in r.checks if c.name == "region")
    assert region.status == "warn"  # not a hard blocker
