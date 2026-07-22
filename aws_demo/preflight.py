"""Sidekick preflight / doctor — flags exactly what a user must set up before the demo can run.

Two classes of blocker:
  1. LOCAL — only **Docker** is truly required; terraform/aws/ansible/helm/kubectl run *inside*
     the operator container, so they're optional-if-you-want-them-by-hand (reported as warnings).
  2. CLOUD — AWS creds, region, per-role permissions, Bedrock model access + the account-level
     invoke restriction we detect and explain.

Each check carries a one-line `fix` so the cockpit can render a do-this-next checklist.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable, List, Optional

# tools the demo uses; docker is the only hard local requirement
_CONTAINER_TOOLS = ["terraform", "aws", "ansible", "helm", "kubectl"]


@dataclass
class Check:
    name: str
    status: str  # "ok" | "fail" | "warn"
    detail: str = ""
    fix: str = ""


@dataclass
class Report:
    checks: List[Check] = field(default_factory=list)

    @property
    def blockers(self) -> List[Check]:
        return [c for c in self.checks if c.status == "fail"]

    @property
    def ready(self) -> bool:
        return not self.blockers

    def add(self, c: Check) -> None:
        self.checks.append(c)


def _version(tool: str) -> Optional[str]:
    if not shutil.which(tool):
        return None
    for flag in ("version", "--version"):
        try:
            out = subprocess.run([tool, flag], capture_output=True, text=True, timeout=6)
            line = (out.stdout or out.stderr).strip().splitlines()
            if line:
                return line[0]
        except Exception:
            pass
    return shutil.which(tool)


def check_local(report: Report) -> None:
    docker = _version("docker")
    report.add(Check(
        "docker", "ok" if docker else "fail", docker or "not installed",
        "" if docker else "Install Docker — https://docs.docker.com/get-docker/ (the ONLY hard local requirement).",
    ))
    for t in _CONTAINER_TOOLS:
        v = _version(t)
        report.add(Check(
            t, "ok" if v else "warn", v or "not installed locally",
            "" if v else f"Optional — {t} runs inside the operator container; install locally only to run it by hand.",
        ))


def check_aws(report: Report, session_factory: Callable[[str], "object"], *, want_region: str = "us-east-1") -> None:
    """session_factory(role) -> boto3.Session. In the demo this is AwsDemoCreds.session."""
    # identity via the readonly role (least privilege) — proves the assume-role chain works
    try:
        sess = session_factory("readonly")
        ident = sess.client("sts").get_caller_identity()
        report.add(Check("aws-credentials", "ok", ident["Arn"]))
        region = getattr(sess, "region_name", None)
        report.add(Check(
            "region", "ok" if region == want_region else "warn", f"region={region}",
            "" if region == want_region else f"Use {want_region} for broad Bedrock/AgentCore availability.",
        ))
    except Exception as e:
        report.add(Check(
            "aws-credentials", "fail", f"cannot assume a demo role ({type(e).__name__})",
            "Create the bootstrap user + roles (infra/terraform/safety) and store them in Vault "
            "(secret/redevops/aws-demo/{bootstrap,config}). See docs/getting-started.md.",
        ))
        return  # nothing else will work without creds

    # deployer perms are a HARD blocker (can't provision without them)
    _probe(report, "perm:deployer(eks)", session_factory, "deployer",
           lambda s: s.client("eks").list_clusters(),
           "Attach infra/iam/deployer-policy.json to the deployer role.", severity="fail")
    # cost + bedrock are WARN — the deploy runs without them (cost monitoring / Bedrock are optional)
    _probe(report, "perm:readonly(cost)", session_factory, "readonly",
           lambda s: s.client("ce").get_cost_and_usage(
               TimePeriod={"Start": "2026-07-01", "End": "2026-07-02"}, Granularity="DAILY", Metrics=["UnblendedCost"]),
           "Attach infra/iam/readonly-policy.json for cost monitoring (not required to deploy).", severity="warn")
    _probe(report, "perm:agent(bedrock)", session_factory, "agent",
           lambda s: s.client("bedrock").list_foundation_models(),
           "Attach infra/iam/agent-policy.json (or AmazonBedrockFullAccess) — optional; demo runs on your model plane.",
           severity="warn")

    _check_bedrock_invoke(report, session_factory)


def _probe(report, label, session_factory, role, fn, fix, *, severity: str = "fail") -> None:
    try:
        fn(session_factory(role))
        report.add(Check(label, "ok", "allowed"))
    except Exception as e:
        report.add(Check(label, severity, f"denied ({type(e).__name__})", fix))


def _check_bedrock_invoke(report, session_factory) -> None:
    """IAM + model access can be green while the ACCOUNT still blocks invoke (new/under-review)."""
    try:
        sess = session_factory("agent")
        sess.client("bedrock-runtime").converse(
            modelId="amazon.nova-micro-v1:0",  # current, cheap; ~$0 for a 1-token probe
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
            inferenceConfig={"maxTokens": 5},
        )
        report.add(Check("bedrock-invoke", "ok", "model invocation works"))
    except Exception as e:
        msg = str(e)
        if "restricted" in msg.lower() or "Customer Agreement" in msg:
            report.add(Check(
                "bedrock-invoke", "warn",
                "account-level restriction (not IAM) — invoke blocked",
                "Bedrock invoke is held on new/under-review accounts. Open an AWS Support case "
                "(service: Bedrock) to lift it, and confirm a payment method. IAM + model access are fine. "
                "The demo runs on your existing model plane meanwhile.",
            ))
        else:
            report.add(Check("bedrock-invoke", "warn", f"could not verify ({type(e).__name__})",
                             "Enable model access in the Bedrock console (us-east-1)."))


def render(report: Report) -> str:
    icon = {"ok": "✓", "fail": "✗", "warn": "•"}
    lines = ["ReDevOps AWS demo — preflight", "=" * 32]
    for c in report.checks:
        lines.append(f"  {icon.get(c.status, '?')} {c.name:22s} {c.detail}")
        if c.fix and c.status != "ok":
            lines.append(f"      → {c.fix}")
    lines.append("")
    lines.append("READY ✓ — you can run the deploy mission." if report.ready
                 else f"BLOCKED — resolve {len(report.blockers)} item(s) above, then re-run the doctor.")
    return "\n".join(lines)
