#!/usr/bin/env bash
# Sidekick preflight — flags exactly what's required before the demo can deploy.
# Only Docker is a hard local requirement; terraform/aws/ansible/helm/kubectl run in the container.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${PY:-$HERE/.venv/bin/python}" -m aws_demo.doctor
