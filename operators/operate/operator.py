"""operate as a Mission Runtime operator — the incident response loop. env-driven so the diagnosis
flows gather→diagnose→remediate→verify without relying on kernel input-threading (real mode reads
Prometheus/Loki + core._run)."""
from __future__ import annotations

import os
import pathlib
import sys

_ROOT = os.environ.get("AGENTIC_OS_ROOT") or str(pathlib.Path(__file__).resolve().parents[2].parent / "agentic-os")
if pathlib.Path(_ROOT).exists() and _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from agentic_os.mission.operator_sdk import Operator, capability  # noqa: E402

from . import core  # noqa: E402


def build_operate_operator(*, env=None, run=None) -> Operator:
    run = run or (env.run if env is not None else core._run)

    def _gather(i):
        ev = core.gather_evidence(i.get("deployment", "outreach-engine"), i.get("namespace", "default"),
                                  signals=(env.signals() if env is not None else None))
        if env is not None:
            env.evidence = ev
        return ev

    def _diagnose(i):
        ev = getattr(env, "evidence", None) if env is not None else None
        dx = core.diagnose(ev or i or {})
        if env is not None:
            env.diagnosis = dx
        return dx

    def _remediate(i):
        fix = (getattr(env, "diagnosis", None) or {}).get("proposed_fix") if env is not None else i.get("fix")
        return core.remediate(fix, run=run)

    def _verify(i):
        return core.verify_health(i.get("deployment", "outreach-engine"), i.get("namespace", "default"),
                                  signals=(env.signals() if env is not None else None))

    return Operator("operate", [
        capability("incident.gather", _gather, provides=["incident_evidence"],
                   permissions=["obs:read"], estimated_value="high", latency_ms=6000),
        capability("incident.diagnose", _diagnose, provides=["incident_diagnosis"],
                   permissions=["obs:read"], estimated_value="high", latency_ms=8000),
        capability("incident.remediate", _remediate, provides=["incident_remediated"],
                   side_effecting=True, approval_required=True, undo="incident.rollback",  # the fix gate
                   permissions=["k8s:write"], estimated_value="high", latency_ms=60000),
        capability("incident.verify", _verify, provides=["incident_verified"],
                   permissions=["obs:read"], estimated_value="high", latency_ms=6000),
    ])
