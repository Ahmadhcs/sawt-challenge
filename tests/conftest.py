import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_SCENARIOS") == "1":
        return

    skip_marker = pytest.mark.skip(reason="set RUN_SCENARIOS=1 to run live-LLM scenario tests")
    for item in items:
        if "scenario" in item.keywords:
            item.add_marker(skip_marker)
