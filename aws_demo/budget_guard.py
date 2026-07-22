"""In-runtime budget guard: read month-to-date spend via the readonly role and act.

This is the *first* line of defence (the authoritative one is the out-of-band Budgets
alarm in infra/terraform/safety/). On TEARDOWN it POSTs a governed teardown mission to
the Mission Runtime rather than mutating anything directly.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import urllib.request

from .budget import BudgetAction, BudgetPolicy
from .creds import AwsDemoCreds


def month_to_date_spend(session) -> float:
    """Unblended MTD cost via Cost Explorer (readonly role)."""
    ce = session.client("ce")
    today = _dt.date.today()
    start = today.replace(day=1).isoformat()
    end = (today + _dt.timedelta(days=1)).isoformat()
    resp = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
    )
    return float(resp["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])


def _open_teardown_mission(mission_api: str) -> None:
    body = json.dumps(
        {"goal": "Budget cap reached — tear down the demo AWS deployment", "template": "teardown_app"}
    ).encode()
    req = urllib.request.Request(
        mission_api.rstrip("/") + "/missions",
        data=body,
        headers={"content-type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=15).read()


def check_and_act(
    cap_usd: float | None = None,
    creds: AwsDemoCreds | None = None,
    mission_api: str | None = None,
) -> tuple[BudgetAction, float]:
    cap_usd = cap_usd if cap_usd is not None else float(os.environ.get("DEMO_BUDGET_USD", "100"))
    creds = creds or AwsDemoCreds()
    mission_api = mission_api or os.environ.get("MISSION_API_URL", "http://localhost:8080")

    spend = month_to_date_spend(creds.session("readonly"))
    action = BudgetPolicy(cap_usd).evaluate(spend)
    if action is BudgetAction.TEARDOWN:
        _open_teardown_mission(mission_api)  # governed; the out-of-band alarm is the real backstop
    return action, spend


if __name__ == "__main__":  # pragma: no cover
    action, spend = check_and_act()
    print(f"budget-guard: MTD ${spend:.2f} -> {action.value}")
