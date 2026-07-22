import os
import pathlib
import sys

import pytest

# The real infra operator lives in the agentic-os repo (apps/infra, package name `infra`).
# We consume it as a dependency; point AGENTIC_OS_APPS at that repo's apps/ dir if it moves.
_AGENTIC_OS_APPS = os.environ.get("AGENTIC_OS_APPS", "/mnt/backup/projects/agentic-os/apps")


@pytest.fixture(scope="session")
def infra_core():
    if not pathlib.Path(_AGENTIC_OS_APPS, "infra", "core.py").exists():
        pytest.skip("agentic-os infra operator not found (set AGENTIC_OS_APPS)")
    if _AGENTIC_OS_APPS not in sys.path:
        sys.path.insert(0, _AGENTIC_OS_APPS)
    import infra.core as core  # noqa: E402

    return core
