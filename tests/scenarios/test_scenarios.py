import pytest

from .definitions import SCENARIOS, run_turns

pytestmark = pytest.mark.scenario


@pytest.mark.parametrize("scenario_name", list(SCENARIOS.keys()))
def test_scenario(scenario_name, tmp_path):
    turns, check = SCENARIOS[scenario_name]
    run = run_turns(turns, tmp_path / "orders.json")
    passed, reason = check(run)
    assert passed, reason
