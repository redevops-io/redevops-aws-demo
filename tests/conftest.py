import os
import pathlib
import sys

import pytest

# The real infra operator lives in the (separate) agentic-os repo — apps/infra, package `infra`.
# We consume it as a dependency. Default assumes agentic-os is checked out alongside this repo;
# override with AGENTIC_OS_APPS if it lives elsewhere. Tests skip cleanly if it isn't present.
_DEFAULT_APPS = pathlib.Path(__file__).resolve().parents[2] / "agentic-os" / "apps"
_AGENTIC_OS_APPS = os.environ.get("AGENTIC_OS_APPS", str(_DEFAULT_APPS))


@pytest.fixture(scope="session")
def infra_core():
    if not pathlib.Path(_AGENTIC_OS_APPS, "infra", "core.py").exists():
        pytest.skip("agentic-os infra operator not found (set AGENTIC_OS_APPS)")
    if _AGENTIC_OS_APPS not in sys.path:
        sys.path.insert(0, _AGENTIC_OS_APPS)
    import infra.core as core  # noqa: E402

    return core
