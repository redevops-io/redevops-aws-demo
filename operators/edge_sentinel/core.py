"""edge-sentinel — ECR image supply-chain: scan → harden → rollout → re-scan.

Injectable seams (`ecr` boto3 client, `run` command runner) so the whole loop is tested/simulated
without touching AWS or a cluster ($0). Real mode uses ECR image scanning + `docker` + `kubectl`.
"""
from __future__ import annotations

import subprocess
from typing import Callable, Optional

Runner = Callable[[list, "Optional[str]"], "tuple[int, str, str]"]


def _run(argv: list, cwd: "Optional[str]" = None):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def scan_ecr(repo: str, tag: str = "latest", *, ecr=None) -> dict:
    """ECR image-scan findings for repo:tag (scan-on-push is enabled in the terraform)."""
    if ecr is None:
        import boto3
        ecr = boto3.client("ecr")
    try:
        ecr.start_image_scan(repositoryName=repo, imageId={"imageTag": tag})
    except Exception:
        pass  # already scanning / scan-on-push already ran
    sf = ecr.describe_image_scan_findings(repositoryName=repo, imageId={"imageTag": tag}).get("imageScanFindings", {})
    counts = sf.get("findingSeverityCounts", {}) or {}
    findings = [
        {"name": f.get("name"), "severity": f.get("severity"),
         "package": ((f.get("attributes") or [{}])[0].get("value"))}
        for f in (sf.get("findings") or [])[:20]
    ]
    crit, high = counts.get("CRITICAL", 0), counts.get("HIGH", 0)
    return {"repo": repo, "tag": tag, "critical": crit, "high": high,
            "severity_counts": counts, "findings": findings,
            "needs_hardening": (crit + high) > 0}


def harden_image(repo: str, registry: str, *, tag: str = "latest", context: str = ".", run: Runner = _run) -> dict:
    """Rebuild on a refreshed base (`--pull` picks up upstream patches) and push to ECR."""
    image = f"{registry}/{repo}:{tag}"
    log = []
    for argv in (["docker", "build", "--pull", "-t", image, context], ["docker", "push", image]):
        rc, out, err = run(argv, None)
        log.append({"cmd": " ".join(argv), "rc": rc})
        if rc != 0:
            return {"ok": False, "image": image, "steps": log, "error": err[-400:]}
    return {"ok": True, "image": image, "steps": log}


def rollout_restart(deployment: str, namespace: str = "default", *, run: Runner = _run) -> dict:
    """kubectl rollout restart + wait — pulls the freshly-pushed hardened image."""
    rc, _, err = run(["kubectl", "rollout", "restart", f"deployment/{deployment}", "-n", namespace], None)
    if rc != 0:
        return {"ok": False, "deployment": deployment, "error": err[-400:]}
    rc2, _, _ = run(["kubectl", "rollout", "status", f"deployment/{deployment}", "-n", namespace, "--timeout=120s"], None)
    return {"ok": rc2 == 0, "deployment": deployment, "namespace": namespace}


def rescan(repo: str, tag: str = "latest", *, ecr=None) -> dict:
    r = scan_ecr(repo, tag, ecr=ecr)
    r["cleared"] = not r["needs_hardening"]
    return r
