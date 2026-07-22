#!/usr/bin/env bash
# HAND-RUNNABLE out-of-band destroy. Works even if Mission Runtime / Sidekick / EKS are down.
# Mirrors what the Budgets->SNS->Lambda->CodeBuild kill-switch does automatically.
#
# Usage:  AWS_PROFILE=redevops-demo ./scripts/emergency-destroy.sh [--yes]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="${EKS_ENV_PATH:-$HERE/infra/terraform/envs/eks}"

echo "⚠  Emergency destroy of the demo EKS env at: $ENV_DIR"
[ "${1:-}" = "--yes" ] || { read -r -p "Type 'destroy' to proceed: " a; [ "$a" = "destroy" ] || { echo "aborted"; exit 1; }; }

if [ -d "$ENV_DIR" ] && [ -n "$(ls -A "$ENV_DIR"/*.tf 2>/dev/null || true)" ]; then
  terraform -chdir="$ENV_DIR" init -input=false >/dev/null
  terraform -chdir="$ENV_DIR" destroy -auto-approve -input=false
else
  echo "no terraform env yet (Phase 1 populates $ENV_DIR) — nothing to destroy"
fi

# Fallback: nuke any cluster left tagged as the demo (defensive; usually a no-op).
if command -v eksctl >/dev/null 2>&1; then
  for c in $(aws eks list-clusters --query 'clusters[]' --output text 2>/dev/null || true); do
    tags=$(aws eks describe-cluster --name "$c" --query 'cluster.tags.demo' --output text 2>/dev/null || true)
    [ "$tags" = "aws" ] && { echo "eksctl delete cluster $c"; eksctl delete cluster --name "$c" --wait || true; }
  done
fi
echo "✔ emergency destroy complete"
