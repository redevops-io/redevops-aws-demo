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

**Next:** Phase 2 (edge-sentinel ECR scan → harden → rollout), then the real `apply` for a recorded run.

## Quickstart (local, no cloud)
```bash
uv venv .venv && uv pip install --python .venv -e ".[dev]"
.venv/bin/pytest                      # 14 tests, zero cloud calls
```

## Bring the cockpit up (mirrors the one-click guide)
```bash
./scripts/up.sh                       # Projects → http://localhost:8080/cockpit
```

## Cloud prerequisites (owner-provisioned — see `infra/terraform/safety/README.md`)
1. Dedicated **us-east-1** account with **Bedrock model access + AgentCore** enabled.
2. `terraform apply` the **safety** module → three roles + Budgets kill-switch.
3. Write Vault: `secret/redevops/aws-demo/{bootstrap,config}`.

Safety is layered: **in-runtime** budget guard + approval gates on every consequential step,
and an **out-of-band** Budgets alarm + auto-destroy that works even if the runtime is down.
No AWS keys live in this repo or in `compose.yml` — Sidekick assumes short-lived roles from Vault.
