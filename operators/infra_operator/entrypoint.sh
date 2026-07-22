#!/usr/bin/env bash
# Runs the agentic-os infra operator (Terraform + Ansible + kubectl) as a Mission Runtime
# /invoke service, pointed at THIS repo's infra/ tree. Sidekick resolves AWS creds from Vault
# (STS assume-role via aws_demo.creds) and injects them as env before the mission calls provision.
set -euo pipefail
export PYTHONPATH="${AGENTIC_OS_APPS:-/opt/agentic-os/apps}:${PYTHONPATH:-}"
export INFRA_DEPLOY_ROOT="${INFRA_DEPLOY_ROOT:-/deploy}"   # mount the repo's infra/ here
echo "infra-operator → deploy_root=$INFRA_DEPLOY_ROOT  port=${PORT:-8230}"
exec uvicorn infra.app:app --host 0.0.0.0 --port "${PORT:-8230}"
