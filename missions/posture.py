"""Governed security-posture missions (Phase 3b) — compliance + privacy.

Both follow: scan → [APPROVAL] → remediate. Compliance checks cluster workloads (CIS); Privacy
discovers PII in S3 — and is active only where a real data source exists.
"""
from __future__ import annotations

import os
import pathlib
import sys

_ROOT = os.environ.get("AGENTIC_OS_ROOT") or str(pathlib.Path(__file__).resolve().parents[2] / "agentic-os")
for _p in (_ROOT, os.path.join(_ROOT, "apps"), str(pathlib.Path(__file__).resolve().parents[1])):
    if pathlib.Path(_p).exists() and _p not in sys.path:
        sys.path.insert(0, _p)

from agentic_os.mission import templates  # noqa: E402
from agentic_os.mission.executor import Executor  # noqa: E402
from agentic_os.mission.operator_sdk import LocalOperatorClient  # noqa: E402
from agentic_os.mission.registry import CapabilityRegistry  # noqa: E402
from agentic_os.mission.runtime import MissionRuntime  # noqa: E402
from agentic_os.mission.store import EventStore  # noqa: E402
from agentic_os.mission.types import ExecutionIntent, IntentStep  # noqa: E402

from operators.agentic_compliance.operator import build_compliance_operator  # noqa: E402
from operators.agentic_privacy.operator import build_privacy_operator  # noqa: E402


def _posture_template(scan_outcome, fix_outcome, scan_need, fix_need):
    def tmpl(mission_id: str) -> ExecutionIntent:
        s_scan = IntentStep(outcome=scan_outcome, need=scan_need, value_hint="high")
        s_fix = IntentStep(outcome=fix_outcome, inputs_from=[scan_outcome], need=fix_need,
                           constraints=["changes production — requires human approval"], value_hint="high")
        return ExecutionIntent(mission_id=mission_id, rationale="posture template", steps=[s_scan, s_fix])
    return tmpl


templates.TEMPLATES.setdefault("compliance_posture", _posture_template(
    "compliance_findings", "compliance_remediated",
    "scan cluster workloads for CIS/compliance violations", "remediate the compliance findings"))
templates.TEMPLATES.setdefault("privacy_posture", _posture_template(
    "privacy_findings", "privacy_remediated",
    "scan data stores for PII exposure", "remediate the PII exposure"))


class SimComplianceEnv:
    def __init__(self):
        # a seeded, intentionally-vulnerable workload
        self.workloads = [{"name": "induced-fault-app", "privileged": True, "runAsRoot": True, "resourceLimits": False}]
        self.findings = None

    def run(self, argv, cwd=None):
        return (0, "ok", "")


class SimPrivacyEnv:
    def __init__(self, with_dataset: bool = True):
        # a tiny synthetic fake-PII dataset (or none → operator reports installed & ready)
        self.buckets = ([{"name": "redevops-demo-pii", "objects": [
            {"key": "customers.csv", "pii": ["email", "ssn"]}]}] if with_dataset else [])
        self.findings = None

    def run(self, argv, cwd=None):
        return (0, "ok", "")


def build_compliance_runtime(env=None) -> MissionRuntime:
    env = env or SimComplianceEnv()
    op = build_compliance_operator(env=env)
    reg = CapabilityRegistry(); reg.register(op.manifest)
    return MissionRuntime(reg, Executor(LocalOperatorClient({"agentic-compliance": op})), store=EventStore())


def build_privacy_runtime(env=None) -> MissionRuntime:
    env = env or SimPrivacyEnv()
    op = build_privacy_operator(env=env)
    reg = CapabilityRegistry(); reg.register(op.manifest)
    return MissionRuntime(reg, Executor(LocalOperatorClient({"agentic-privacy": op})), store=EventStore())


def create_compliance_mission(rt, goal="Scan cluster posture and remediate compliance findings"):
    m = rt.create_mission(goal, policy_refs=["compliance:read", "k8s:write"], template="compliance_posture")
    rt.run(m.id)
    return m


def create_privacy_mission(rt, goal="Scan data stores for PII and remediate exposure"):
    m = rt.create_mission(goal, policy_refs=["privacy:read", "s3:write"], template="privacy_posture")
    rt.run(m.id)
    return m
