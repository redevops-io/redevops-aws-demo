# redevops-aws-demo

A **self-demonstrating** ReDevOps × AWS demo: this repo *contains* the Terraform + Ansible
it deploys, so one prompt in **Projects** deploys it onto AWS and then **secures, hardens,
monitors, and heals** it — every consequential step gated, inspectable, and replayable.

See [`PLAN.md`](PLAN.md) for the full architecture, phases, and decisions.

```
Projects (human control plane)
   │  one sentence
   ▼
Mission Runtime ── governs plan · gate · verify · saga · replay
   │
   ├── Context Runtime ── decides retrieval arm + model per step
   └── Sidekick ──────── DevOps agent: Vault→STS, terraform/ansible/kubectl, monitor loop
                          │
                          ▼  (real EKS in a dedicated us-east-1 account)
                  EKS + Helm monitoring + edge-sentinel + Agentic Compliance/Privacy
```

## Status

**Phase 0 — scaffold + safety rails ($0)** ✅
- Vault → STS **assume-role** cred helper (`aws_demo/creds.py`) — tested (moto), no key leaks
- In-runtime **budget policy + guard** + **out-of-band kill-switch** Terraform (`terraform validate` clean)
- Attachable **IAM policies** (`infra/iam/`) + safety roles + scripts

**Phase 1 — governed deploy spine (sim-first, $0)** ✅
- Trimmed **EKS env + Helm monitoring** Terraform — `terraform plan` = **68 real resources, $0**
- Real **infra operator** wired to `infra/terraform/envs/aws` (`/invoke` service)
- **Deploy-and-operate mission** runs in-process: scan → plan → **⛔ approval gate** (plan + cost
  evidence, ~$0.31/hr) → provision → configure → verify; **18 tests green**
- Run it: `SIM=1 python -m missions.deploy_operate`

**Onboarding — Sidekick tells you what's required** ✅
- Preflight is a **cloud-agnostic Sidekick skill** (`deployment-preflight`) that gates every deploy
  mission (node 0), shared across AWS/GCP/Azure/DigitalOcean — only the CLI + Terraform syntax differ.
  `aws_demo/preflight.py` is its executable AWS binding (exposable as an MCP `preflight_check` tool);
  run it by hand with `./scripts/doctor.sh` for a ✓/✗ checklist + the **exact fix** per item.
- It detects creds, region, per-role permissions, and the **Bedrock account-invoke restriction** (with
  the support-case fix). Hard blockers are only Docker + creds + deployer perms; cost/Bedrock are warnings.
- **Only Docker is required locally** — terraform/aws/ansible/helm/kubectl all run in the operator
  container (macOS/Windows/Linux install matrix in the skill + [docs/getting-started.md](docs/getting-started.md)).

**Phase 2 — edge-sentinel supply-chain hardening (sim-first, $0)** ✅
- `operators/edge_sentinel/` — `sentinel.scan` (ECR image findings; also provides `image_scanned`) ·
  `sentinel.harden` (gated rebuild `--pull` + push) · `sentinel.rollout` (`kubectl rollout restart`) ·
  `sentinel.rescan` (confirm cleared)
- **Governed harden loop** (`missions/harden_images.py`): scan finds a seeded CVE → **⛔ "harden?" gate**
  → approve → rebuild+push → rollout → re-scan **cleared** (reject hardens nothing). **26 tests green.**
- Run it: `APPROVE=1 python -m missions.harden_images`

**Phase 3 — operate loop + security posture (sim-first, $0)** ✅
- **Induced-fault operate loop** (`missions/incident_response.py`, the "wow"): rising restarts →
  gather evidence → diagnose (*memory limit too low*) → **⛔ remediation gate** → raise memory →
  **verify healthy**. Models CloudWatch/Prometheus alarm → incident mission (no silent mutation).
- **Agentic Compliance + Privacy** (`missions/posture.py`): CIS scan of a seeded vulnerable workload;
  PII scan of a synthetic dataset (**inactive with no data source — never fakes findings**). The
  kernel marks the whole compliance/privacy domain **regulatory → even the scan is gated**.
- Run: `APPROVE=1 python -m missions.incident_response`. **34 tests green.**

**Next:** Phase 4 (Bedrock/AgentCore/Strands + outreach capstone), then the real `apply` for a recorded run.

## Quickstart (local, no cloud)
```bash
uv venv .venv && uv pip install --python .venv -e ".[dev]"
.venv/bin/pytest                      # 14 tests, zero cloud calls
```

## Bring the cockpit up (mirrors the one-click guide)
```bash
./scripts/up.sh                       # Projects → http://localhost:8080/cockpit
```

## Run the demo — Sidekick governing the five operators

The deploy-and-operate operators run as their own `/invoke` services (one image,
`operators/service.py`, `OPERATOR` selects which). Sidekick **federates** them from
`operators/modules.yaml` — it discovers each manifest over `GET /capabilities` and drives the
missions over `POST /invoke`, without importing the operator code (see
`agentic-os/deploy/sidekick-devops/federation.py`).

```bash
# $0 dry run — every operator short-circuits to its in-process simulator:
SIM=1 docker compose -f deploy/compose.demo.yml up --build

# Real mode (SIM=0, default): operators shell out to terraform/aws/kubectl.
# Sidekick injects Vault→STS short-lived creds before the provision gate.
docker compose -f deploy/compose.demo.yml up --build
```
Then open the Projects cockpit at http://localhost:8000/cockpit and start the deploy mission — it
plans + scans, pauses at the provision approval gate with the terraform plan + cost estimate, then
provisions → configures → verifies across the federated operators. `AGENTIC_OS_ROOT` defaults to a
sibling `agentic-os` checkout.

| service | port | operator |
|---|---|---|
| infra | 8230 | terraform/ansible provision · configure · verify · drift |
| edge-sentinel | 8241 | ECR/Inspector scan → harden → rollout → rescan |
| operate | 8242 | incident: gather → diagnose → remediate → verify |
| agentic-compliance | 8243 | CIS/OpenSCAP posture scan → gated remediation |
| agentic-privacy | 8244 | PII/data-map scan (active only where a data source exists) |
| sidekick | 8000 | Projects cockpit + Mission Runtime governing the above |

## Cloud prerequisites (owner-provisioned — see `infra/terraform/safety/README.md`)
1. Dedicated **us-east-1** account with **Bedrock model access + AgentCore** enabled.
2. `terraform apply` the **safety** module → three roles + Budgets kill-switch.
3. Write Vault: `secret/redevops/aws-demo/{bootstrap,config}`.

Safety is layered: **in-runtime** budget guard + approval gates on every consequential step,
and an **out-of-band** Budgets alarm + auto-destroy that works even if the runtime is down.
No AWS keys live in this repo or in `compose.yml` — Sidekick assumes short-lived roles from Vault.
