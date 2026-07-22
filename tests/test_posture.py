"""Phase 3b — Agentic Compliance + Privacy, governed, $0, against seeded conditions.

Note: the kernel marks the compliance/privacy DOMAIN regulatory, so even the *scan* is approval-gated
(regulatory oversight by design). These missions therefore gate at scan AND remediate.
"""
import missions.posture as p
from agentic_os.mission.types import MissionState

from operators.agentic_compliance import core as ccore
from operators.agentic_privacy import core as pcore


def _walk(rt, m, decision="approve", max_gates=6):
    for _ in range(max_gates):
        if m.state.value in ("succeeded", "failed", "cancelled"):
            break
        if m.state == MissionState.WAITING_HUMAN:
            pend = rt.repo.pending_human(m.id)
            rt.approve(m.id, pend["node_id"], decision)
        if m.state == MissionState.RUNNING:
            rt.run(m.id)
    return m


def test_compliance_is_regulatory_gated_and_remediates():
    env = p.SimComplianceEnv()
    rt = p.build_compliance_runtime(env)
    m = p.create_compliance_mission(rt)

    # regulatory: even the compliance SCAN is gated first
    assert m.state == MissionState.WAITING_HUMAN
    assert "compliance.scan" in rt.repo.pending_human(m.id)["capability"]

    _walk(rt, m, "approve")
    assert m.state == MissionState.SUCCEEDED
    # the seeded privileged/root/no-limits workload was found
    assert env.findings and any(f["control"] == "CIS-5.2.1" for f in env.findings)


def test_compliance_reject_stops():
    env = p.SimComplianceEnv()
    rt = p.build_compliance_runtime(env)
    m = p.create_compliance_mission(rt)
    pend = rt.repo.pending_human(m.id)
    rt.approve(m.id, pend["node_id"], "reject")
    if m.state == MissionState.RUNNING:
        rt.run(m.id)
    assert m.state != MissionState.SUCCEEDED


def test_privacy_active_with_dataset_finds_pii():
    env = p.SimPrivacyEnv(with_dataset=True)
    rt = p.build_privacy_runtime(env)
    m = p.create_privacy_mission(rt)
    assert m.state == MissionState.WAITING_HUMAN  # regulatory
    _walk(rt, m, "approve")
    assert m.state == MissionState.SUCCEEDED
    assert env.findings and env.findings[0]["pii_types"] == ["email", "ssn"]


def test_privacy_inactive_without_data_source_makes_no_findings():
    # the key rule: installed & ready, NOT manufacturing empty findings
    r = pcore.scan_pii(buckets=None)
    assert r["active"] is False and r["findings"] == [] and r["needs_remediation"] is False


def test_compliance_scan_maps_controls():
    r = ccore.scan_posture([{"name": "x", "privileged": True}])
    assert r["needs_remediation"] and r["findings"][0]["control"] == "CIS-5.2.1"
