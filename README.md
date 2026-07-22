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

## Status — Phase 0 (scaffold + safety rails, $0)

| Piece | State |
|---|---|
| Vault → STS **assume-role** cred helper (`aws_demo/creds.py`) | ✅ built + tested (moto) |
| In-runtime **budget policy + guard** (`aws_demo/budget.py`, `budget_guard.py`) | ✅ built + tested |
| **Out-of-band kill-switch** Terraform (roles + Budgets → SNS → Lambda → CodeBuild destroy) | ✅ `terraform validate` clean |
| `emergency-destroy.sh` / `budget-guard.sh` / `up.sh` / `teardown.sh` | ✅ |
| Local `compose.yml` (Projects + Context Runtime) | ✅ skeleton (operators land in Phase 1) |
| Phase 1+ (EKS env, operators, monitor, context arms) | ⬜ next |

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
