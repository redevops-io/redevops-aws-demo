#!/usr/bin/env bash
# In-runtime budget guard: reads MTD spend (readonly role) and, past the cap, opens a
# governed teardown mission. The authoritative backstop is the out-of-band Budgets alarm.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${PY:-$HERE/.venv/bin/python}" -m aws_demo.budget_guard
