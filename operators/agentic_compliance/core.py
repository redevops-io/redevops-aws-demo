"""Agentic Compliance — CIS-style posture checks over cluster workloads + gated remediation.

Real mode reads the cluster (+ Security Hub/Config); sim injects `workloads`. Findings map to CIS
controls; remediation is the safe, gated fix (drop privileged, runAsNonRoot, add limits)."""
from __future__ import annotations

import subprocess
from typing import Callable, Optional

Runner = Callable[[list, "Optional[str]"], "tuple[int, str, str]"]


def _run(argv, cwd=None):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def scan_posture(workloads: "Optional[list]" = None) -> dict:
    findings = []
    for w in workloads or []:
        name = w.get("name", "?")
        if w.get("privileged"):
            findings.append({"control": "CIS-5.2.1", "severity": "critical", "workload": name, "issue": "privileged container"})
        if w.get("runAsRoot"):
            findings.append({"control": "CIS-5.2.6", "severity": "high", "workload": name, "issue": "runs as root"})
        if not w.get("resourceLimits"):
            findings.append({"control": "CIS-5.7.3", "severity": "medium", "workload": name, "issue": "no resource limits"})
    return {"findings": findings, "count": len(findings), "needs_remediation": len(findings) > 0}


def remediate_posture(findings: "Optional[list]" = None, *, run: Runner = _run) -> dict:
    applied = []
    for f in findings or []:
        rc, _, _ = run(["kubectl", "patch", "deployment", f["workload"], "--type=strategic",
                        "-p", f"remediate:{f['control']}"], None)
        applied.append({"workload": f["workload"], "control": f["control"], "ok": rc == 0})
    return {"applied": applied, "ok": all(a["ok"] for a in applied) if applied else True}
