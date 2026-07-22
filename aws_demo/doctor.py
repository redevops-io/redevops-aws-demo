"""`python -m aws_demo.doctor` — run the preflight and print the checklist.

Works in two credential modes so no user is forced into Vault:
  • governed: Vault + STS assume-role (AwsDemoCreds) — the team/demo default
  • solo:     the standard boto3 chain (~/.aws or env vars) if Vault/config isn't set
"""
from __future__ import annotations

import os

import boto3

from .creds import AwsDemoCreds
from .preflight import Report, check_aws, check_local, render


def session_factory():
    """Return role -> boto3.Session. Prefer Vault assume-role; fall back to the ambient profile."""
    try:
        creds = AwsDemoCreds()
        _ = creds.region  # forces a Vault read; raises if Vault/config absent
        return creds.session
    except Exception:
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
        ambient = boto3.Session(region_name=region)
        return lambda role: ambient  # same ambient creds for every "role" in solo mode


def main() -> int:
    report = Report()
    check_local(report)
    try:
        check_aws(report, session_factory())
    except Exception as e:  # noqa: BLE001
        report.add_fail = None  # type: ignore
        from .preflight import Check
        report.add(Check("aws", "fail", f"preflight aborted ({type(e).__name__})",
                         "See docs/getting-started.md for AWS account + credential setup."))
    print(render(report))
    return 0 if report.ready else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
