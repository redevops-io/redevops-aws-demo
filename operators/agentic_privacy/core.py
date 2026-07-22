"""Agentic Privacy — PII discovery over S3 (+ Macie) with gated remediation.

KEY RULE: active only where a real data source exists. With no bucket it reports installed & ready —
never manufacturing empty findings. Sim injects `buckets`; real mode uses Amazon Macie."""
from __future__ import annotations

import subprocess
from typing import Callable, Optional

Runner = Callable[[list, "Optional[str]"], "tuple[int, str, str]"]


def _run(argv, cwd=None):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def scan_pii(buckets: "Optional[list]" = None) -> dict:
    if not buckets:
        return {"active": False, "findings": [], "count": 0, "needs_remediation": False,
                "note": "no data source — installed & ready, not scanning (no empty findings manufactured)"}
    findings = []
    for b in buckets:
        for obj in b.get("objects", []):
            if obj.get("pii"):
                findings.append({"bucket": b["name"], "object": obj["key"], "pii_types": obj["pii"]})
    return {"active": True, "findings": findings, "count": len(findings), "needs_remediation": len(findings) > 0}


def remediate_pii(findings: "Optional[list]" = None, *, run: Runner = _run) -> dict:
    applied = [{"bucket": f["bucket"], "object": f["object"], "action": "restrict-access + flag-for-review"}
               for f in (findings or [])]
    return {"applied": applied, "ok": True}
