"""operate — the induced-fault incident loop: gather → diagnose → remediate → verify.

Rule-based diagnosis (LLM-optional): OOM restarts ⇒ the memory limit is too low ⇒ raise it (or roll
back). Injectable `run` so remediation is tested without a cluster ($0).
"""
from __future__ import annotations

import subprocess
from typing import Callable, Optional

Runner = Callable[[list, "Optional[str]"], "tuple[int, str, str]"]


def _run(argv: list, cwd: "Optional[str]" = None):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def gather_evidence(deployment: str, namespace: str = "default", *, signals: "Optional[dict]" = None) -> dict:
    """Restart count, OOM events, recent logs, runbook match. `signals` is injected in sim; real mode
    would read Prometheus (restarts) + Loki (logs) + a runbook lookup."""
    ev = dict(signals) if signals is not None else {"restarts": 0, "oom": False, "logs": [], "runbook": None}
    ev.setdefault("deployment", deployment)
    ev.setdefault("namespace", namespace)
    return ev


def diagnose(evidence: dict) -> dict:
    """Root-cause the fault. OOMKilled / repeated restarts ⇒ memory limit too low."""
    if evidence.get("oom") or evidence.get("restarts", 0) >= 3:
        return {
            "root_cause": "container memory limit too low — OOMKilled → periodic restarts",
            "confidence": 0.9,
            "proposed_fix": {"action": "raise_memory", "deployment": evidence["deployment"],
                             "namespace": evidence.get("namespace", "default"),
                             "from": evidence.get("memory_limit", "256Mi"), "to": "512Mi"},
            "alternatives": ["rollback to the prior revision"],
        }
    return {"root_cause": "no clear fault", "confidence": 0.2, "proposed_fix": None}


def remediate(fix: "Optional[dict]", *, run: Runner = _run) -> dict:
    if not fix:
        return {"ok": False, "note": "no fix proposed"}
    ns = fix.get("namespace", "default")
    if fix["action"] == "raise_memory":
        rc, _, err = run(["kubectl", "set", "resources", f"deployment/{fix['deployment']}",
                          "-n", ns, f"--limits=memory={fix['to']}"], None)
    elif fix["action"] == "rollback":
        rc, _, err = run(["kubectl", "rollout", "undo", f"deployment/{fix['deployment']}", "-n", ns], None)
    else:
        return {"ok": False, "note": f"unknown action {fix['action']}"}
    return {"ok": rc == 0, "applied": fix, "error": (err[-300:] if rc else "")}


def verify_health(deployment: str, namespace: str = "default", *, signals: "Optional[dict]" = None) -> dict:
    s = signals if signals is not None else {"restarts": 0, "oom": False}
    healthy = not (s.get("oom") or s.get("restarts", 0) >= 3)
    return {"deployment": deployment, "healthy": healthy, "restarts": s.get("restarts", 0)}
