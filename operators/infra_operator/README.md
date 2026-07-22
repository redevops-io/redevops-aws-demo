# infra_operator — Terraform/Ansible/kubectl driver (Mission Runtime `/invoke`)

Thin service wrapper around the **real** agentic-os infra operator (`apps/infra`), pointed at
this repo's `infra/` tree via `INFRA_DEPLOY_ROOT`. Exposes `GET /capabilities`, `POST /invoke`,
`GET /health` — the capabilities the `deploy_app` mission composes:

`infra.plan · infra.provision (gated, undo=infra.destroy_delta) · infra.configure · infra.verify · infra.drift`

- `provision` runs `terraform -chdir=infra/terraform/envs/aws apply`; `configure` runs Ansible;
  `verify` smoke-tests `/health`+`/capabilities`. All commands target this repo (proven in
  `tests/test_infra_operator.py`).
- **Creds:** never baked in. Sidekick assumes the `deployer` role from Vault (`aws_demo.creds`)
  and passes short-lived AWS_* env to this service per provision.

Run locally: mount `agentic-os/apps → /opt/agentic-os/apps` and `./infra → /deploy`, then the
container serves on `:8230`.
