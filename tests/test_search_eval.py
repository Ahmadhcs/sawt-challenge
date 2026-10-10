"""
Honest accuracy check for search_menu against realistic Saudi caller phrasings.

This is an evaluation, not a pass/fail gate: the threshold/scoring in
restaurant_db.py should not be tuned specifically to make these numbers look
good. Run directly to see the full report:

    .venv/bin/python -m tests.test_search_eval

Three separate numbers are tracked:
- "before": the original 26-case set, scored against the pre-fix WRatio-only
  ranking (recorded once, kept as a fixed reference point - see BEFORE_RESULT).
- "after": the same 26 cases, scored against the current ranking.
- "held-out": 10 new cases written after the fix, never used to tune it.
"""

from src.restaurant_db import search_menu


BEFORE_RESULT = {"top1_accuracy": 0.85, "top3_accuracy": 0.85, "misses": 4}

EVAL_CASES = [
    ("شاورما دجاج", "sandwiches_07", "direct"),
    ("شاورمه", "sandwiches_07", "dialect spelling"),
    ("بيتزا مارغريتا", "pizza_flatbread_01", "direct"),
    ("بتزا مارغريتا", "pizza_flatbread_01", "typo"),
    ("مارغريتا", "pizza_flatbread_01", "one-word"),
    ("حمص", "appetizers_01", "one-word, ambiguous with حمص باللحم"),
    ("متبل", "appetizers_03", "one-word"),
    ("كبسة دجاج", "rice_01", "direct"),
    ("كبسه دجاج", "rice_01", "dialect spelling"),
    ("مندي لحم", "rice_04", "direct"),
    ("ابغى برجر لحم مع جبن", "sandwiches_01", "natural phrasing"),
    ("ابغى تشكن برجر", "sandwiches_04", "transliterated 'chicken', not in synonym map"),
    ("عطيني لارج بيتزا مارغريتا", "pizza_flatbread_01", "transliterated 'large', not in synonym map"),
    ("عصير برتقال بدون ثلج", "beverages_04", "code-switching via بدون"),
    ("دجاج مقرمش", "chicken_03", "real word 'مقرمش' vs menu's 'كرسبي'"),
    ("روبيان مشوي", "seafood_04", "direct"),
    ("كنافة", "desserts_01", "one-word, ambiguous with كنافة بالقشطة"),
    ("ام علي", "desserts_03", "dropped-hamza spelling of أم علي"),
    ("سلطة فتوش", "salads_soups_05", "direct"),
    ("شوربة عدس", "salads_soups_01", "direct"),
    ("بسبوسة", "desserts_05", "one-word"),
    ("تميس بالجبن", "breakfast_04", "direct"),
    ("فول", "breakfast_02", "one-word, ambiguous with فول قلابة"),
    ("لازانيا لحم", "pasta_06", "direct, ambiguous with لازانيا خضار"),
    ("قهوة سعودية", "beverages_10", "direct, ambiguous with قهوة أمريكية"),
    ("ديناميت شرمب", "seafood_06", "partially-English item name"),
]

HELD_OUT_CASES = [
    ("بطاطس حارة", "appetizers_10", "direct"),
    ("اجنحة دجاج", "appetizers_11", "dropped-hamza spelling of أجنحة"),
    ("ستيك", "grills_10", "one-word"),
    ("برياني روبيان", "rice_09", "direct"),
    ("بريني دجاج", "rice_08", "typo (missing ا in برياني)"),
    ("سلطة سيزر", "salads_soups_08", "partial name"),
    ("ابغى حلوم", "breakfast_11", "natural phrasing"),
    ("عطيني سبايسي بطاطس", "appetizers_10", "transliterated 'spicy', not in synonym map"),
    ("جريش", "rice_11", "one-word"),
    ("ستيك لحم مديم", "grills_10", "transliterated 'medium', not in SIZE_KEYWORDS"),
]


def _evaluate(cases: list[tuple[str, str, str]]) -> dict:
    rows = []
    top1_hits = 0
    top3_hits = 0

    for query, expected_item_id, note in cases:
        results = search_menu(query)
        result_ids = [r.item_id for r in results]

        top1 = result_ids[0] == expected_item_id if result_ids else False
        top3 = expected_item_id in result_ids[:3]

        top1_hits += top1
        top3_hits += top3

        rows.append(
            {
                "query": query,
                "expected": expected_item_id,
                "got": result_ids,
                "note": note,
                "top1": top1,
                "top3": top3,
            }
        )

    total = len(cases)
    return {
        "rows": rows,
        "top1_accuracy": top1_hits / total,
        "top3_accuracy": top3_hits / total,
    }


def _print_report(label: str, report: dict) -> None:
    misses = [r for r in report["rows"] if not r["top3"]]
    print(f"\n--- {label} ---")
    print(f"top-1 accuracy: {report['top1_accuracy']:.0%}")
    print(f"top-3 accuracy: {report['top3_accuracy']:.0%}")
    if misses:
        print(f"{len(misses)} miss(es) (expected not in top-3):")
        for r in misses:
            print(f"  '{r['query']}' -> expected {r['expected']}, got {r['got']} ({r['note']})")


def test_search_eval_report():
    after = _evaluate(EVAL_CASES)
    held_out = _evaluate(HELD_OUT_CASES)

    print(f"\nbefore: top-1={BEFORE_RESULT['top1_accuracy']:.0%} top-3={BEFORE_RESULT['top3_accuracy']:.0%}")
    _print_report("after (same 26 cases)", after)
    _print_report("held-out (10 new cases)", held_out)

    assert after["top3_accuracy"] >= 0.6
    assert held_out["top3_accuracy"] >= 0.5


if __name__ == "__main__":
    after = _evaluate(EVAL_CASES)
    held_out = _evaluate(HELD_OUT_CASES)

    print(f"before: top-1={BEFORE_RESULT['top1_accuracy']:.0%} top-3={BEFORE_RESULT['top3_accuracy']:.0%}")
    _print_report("after (same 26 cases)", after)
    _print_report("held-out (10 new cases)", held_out)
