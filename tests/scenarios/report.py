"""
Runs every scenario in definitions.py 3 times against the real agent (GPT-4.1)
and prints a markdown results table. This burns real API calls - run it
deliberately, not as part of normal pytest.

    RUN_SCENARIOS=1 .venv/bin/python -m tests.scenarios.report
"""

import tempfile
import traceback
from pathlib import Path

from .definitions import SCENARIOS, run_turns

RUNS_PER_SCENARIO = 3


def _run_once(turns: list[str], check) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        orders_path = Path(tmp_dir) / "orders.json"
        try:
            run = run_turns(turns, orders_path)
        except Exception as e:
            return False, f"exception: {e}"
        return check(run)


def main() -> None:
    rows = []
    for name, (turns, check) in SCENARIOS.items():
        results = []
        for attempt in range(1, RUNS_PER_SCENARIO + 1):
            try:
                passed, reason = _run_once(turns, check)
            except Exception:
                passed, reason = False, traceback.format_exc(limit=1)
            results.append((passed, reason))
            print(f"[{name}] attempt {attempt}/{RUNS_PER_SCENARIO}: {'PASS' if passed else 'FAIL - ' + reason}")

        pass_count = sum(1 for passed, _ in results if passed)
        failures = [reason for passed, reason in results if not passed]
        rows.append((name, pass_count, RUNS_PER_SCENARIO, failures))

    print("\n--- Results table (paste into DESIGN.md) ---\n")
    print("| Scenario | Pass rate | Failures |")
    print("|---|---|---|")
    for name, pass_count, total, failures in rows:
        failure_text = "; ".join(failures) if failures else "-"
        print(f"| {name} | {pass_count}/{total} | {failure_text} |")


if __name__ == "__main__":
    main()
