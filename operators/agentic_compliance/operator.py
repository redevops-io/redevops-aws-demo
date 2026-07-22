from __future__ import annotations
import os, pathlib, sys
_ROOT = os.environ.get("AGENTIC_OS_ROOT") or str(pathlib.Path(__file__).resolve().parents[2].parent / "agentic-os")
if pathlib.Path(_ROOT).exists() and _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from agentic_os.mission.operator_sdk import Operator, capability  # noqa: E402
from . import core  # noqa: E402


def build_compliance_operator(*, env=None, run=None) -> Operator:
    run = run or (env.run if env is not None else core._run)

    def _scan(i):
        r = core.scan_posture(env.workloads if env is not None else i.get("workloads"))
        if env is not None:
            env.findings = r["findings"]
        return r

    def _remediate(i):
        f = getattr(env, "findings", None) if env is not None else i.get("findings")
        return core.remediate_posture(f, run=run)

    return Operator("agentic-compliance", [
        capability("compliance.scan", _scan, provides=["compliance_findings"],
                   permissions=["compliance:read"], estimated_value="high", latency_ms=9000),
        capability("compliance.remediate", _remediate, provides=["compliance_remediated"],
                   side_effecting=True, approval_required=True, permissions=["k8s:write"],
                   estimated_value="high", latency_ms=45000),
    ])
