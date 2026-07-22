"""Phase 3 — the induced-fault operate loop, in-process, $0.

Rising restarts → gather → diagnose (memory too low) → pause at the remediation gate → approve →
raise memory → verify healthy. Reject → production untouched, no fix applied.
"""
import missions.incident_response as ir
from agentic_os.mission.types import MissionState


def test_detects_diagnoses_gates_and_heals():
    env = ir.SimIncidentEnv()
    rt = ir.build_runtime(env)
    m = ir.create_incident_mission(rt)

    # evidence gathered + diagnosed, then paused at the remediation gate
    assert m.state == MissionState.WAITING_HUMAN
    assert env.diagnosis and "memory limit too low" in env.diagnosis["root_cause"]
    assert env.diagnosis["proposed_fix"]["action"] == "raise_memory"
    assert env.remediated is False  # nothing changed before approval

    pending = rt.repo.pending_human(m.id)
    rt.approve(m.id, pending["node_id"], "approve")
    if m.state not in (MissionState.SUCCEEDED, MissionState.FAILED):
        rt.run(m.id)
    assert m.state == MissionState.SUCCEEDED
    assert env.remediated is True
    # post-fix signals are healthy
    assert env.signals()["oom"] is False and env.signals()["restarts"] == 0


def test_reject_leaves_production_untouched():
    env = ir.SimIncidentEnv()
    rt = ir.build_runtime(env)
    m = ir.create_incident_mission(rt)
    pending = rt.repo.pending_human(m.id)

    rt.approve(m.id, pending["node_id"], "reject")
    if m.state == MissionState.RUNNING:
        rt.run(m.id)
    assert m.state != MissionState.SUCCEEDED
    assert env.remediated is False  # rejected → no kubectl change


def test_diagnose_is_rulebased():
    from operators.operate import core
    healthy = core.diagnose({"deployment": "x", "restarts": 0, "oom": False})
    assert healthy["proposed_fix"] is None
    faulty = core.diagnose({"deployment": "x", "oom": True})
    assert faulty["proposed_fix"]["action"] == "raise_memory"
