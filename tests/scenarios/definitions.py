import json
from dataclasses import dataclass, field
from pathlib import Path

from src.agent import ToolCallRecord, respond
from src.order_state import OrderState
from src.tools import CallSession


@dataclass
class ScenarioRun:
    session: CallSession
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    turn_snapshots: list[dict] = field(default_factory=list)  # order.summary() after each turn


def run_turns(turns: list[str], orders_path: Path) -> ScenarioRun:
    session = CallSession(order=OrderState(), orders_path=orders_path)
    history: list[dict[str, str]] = []
    tool_calls: list[ToolCallRecord] = []
    turn_snapshots: list[dict] = []

    for turn_text in turns:
        reply = respond(session, history, turn_text)
        tool_calls.extend(reply.tool_calls)
        history.append({"role": "user", "content": turn_text})
        history.append({"role": "assistant", "content": reply.text})
        turn_snapshots.append(session.order.summary())

    return ScenarioRun(session=session, tool_calls=tool_calls, turn_snapshots=turn_snapshots)


def _tool_names(run: ScenarioRun) -> list[str]:
    return [tc.name for tc in run.tool_calls]


def check_1_delivery_to_pickup(run: ScenarioRun) -> tuple[bool, str]:
    order = run.session.order
    if order.service_type != "pickup":
        return False, f"expected service_type=pickup, got {order.service_type!r}"
    if order.delivery_fee_halalas != 0:
        return False, f"expected delivery_fee_halalas=0, got {order.delivery_fee_halalas}"
    if len(order.lines) != 2:
        return False, f"expected 2 lines unchanged, got {len(order.lines)}"
    return True, "ok"


def check_2_unavailable_after_branch_change(run: ScenarioRun) -> tuple[bool, str]:
    order = run.session.order
    if order.branch_id != "jed_rawdah":
        return False, f"expected branch_id=jed_rawdah, got {order.branch_id!r}"
    if not order.unavailable_line_ids:
        return False, "expected a flagged unavailable line, got none"
    if order.status == "confirmed":
        return False, "order was confirmed despite an unavailable line"
    confirm_calls = [tc for tc in run.tool_calls if tc.name == "confirm_order"]
    if confirm_calls and confirm_calls[-1].result.get("ok") is not False:
        return False, "confirm_order did not return an error for the unavailable line"
    return True, "ok"


def check_3_remove_then_fresh_readback(run: ScenarioRun) -> tuple[bool, str]:
    order = run.session.order
    readback_calls = [tc for tc in run.tool_calls if tc.name == "get_order_summary"]
    if len(readback_calls) < 2:
        return False, f"expected >=2 get_order_summary calls (fresh read-back after removal), got {len(readback_calls)}"
    if len(order.lines) != 1:
        return False, f"expected 1 line remaining after removal, got {len(order.lines)}"
    if order.status != "confirmed":
        return False, f"expected order confirmed, got status={order.status!r}"
    expected_total = 4200
    if order.total_halalas != expected_total:
        return False, f"expected total_halalas={expected_total}, got {order.total_halalas}"
    return True, "ok"


def check_4_everything_in_one_sentence(run: ScenarioRun) -> tuple[bool, str]:
    first_turn = run.turn_snapshots[0]
    if first_turn["service_type"] != "delivery":
        return False, f"expected service_type=delivery after turn 1, got {first_turn['service_type']!r}"
    if first_turn["zone_id"] != "yasmin":
        return False, f"expected zone_id=yasmin after turn 1, got {first_turn['zone_id']!r}"

    order = run.session.order
    if len(order.lines) != 1:
        return False, f"expected 1 line at the end, got {len(order.lines)}"
    line = order.lines[0]
    if not line.item_id.startswith("sandwiches_"):
        return False, f"expected a shawarma/sandwich item, got {line.item_id!r}"
    if line.qty != 2:
        return False, f"expected qty=2, got {line.qty}"
    return True, "ok"


def check_5_quantity_correction(run: ScenarioRun) -> tuple[bool, str]:
    order = run.session.order
    if len(order.lines) != 1:
        return False, f"expected 1 line, got {len(order.lines)}"
    if order.lines[0].qty != 3:
        return False, f"expected qty=3 after correction, got {order.lines[0].qty}"
    if "update_item" not in _tool_names(run):
        return False, "agent never called update_item for the correction"
    return True, "ok"


def check_6_complaint_transfers(run: ScenarioRun) -> tuple[bool, str]:
    if not run.session.transferred:
        return False, "expected session.transferred=True"
    if "transfer_to_human" not in _tool_names(run):
        return False, "transfer_to_human was never called"
    return True, "ok"


def check_7_idempotent_confirm(run: ScenarioRun) -> tuple[bool, str]:
    order = run.session.order
    if order.status != "confirmed":
        return False, f"expected status=confirmed, got {order.status!r}"
    if order.order_id is None:
        return False, "expected order_id to be set"

    confirm_calls = [tc for tc in run.tool_calls if tc.name == "confirm_order"]
    successful = [tc for tc in confirm_calls if tc.result.get("ok")]
    order_ids = {tc.result.get("order_id") for tc in successful}
    if len(order_ids) > 1:
        return False, f"expected one consistent order_id across confirms, got {order_ids}"

    orders_path = run.session.orders_path
    if not orders_path.exists():
        return False, "orders file was never written"
    with open(orders_path, encoding="utf-8") as f:
        records = json.load(f)
    if len(records) != 1:
        return False, f"expected exactly 1 record in orders file, got {len(records)}"

    return True, "ok"


def check_8_code_switching_qty_and_meal(run: ScenarioRun) -> tuple[bool, str]:
    order = run.session.order
    if len(order.lines) != 1:
        return False, f"expected 1 line, got {len(order.lines)}"
    line = order.lines[0]
    if not line.item_id.startswith("sandwiches_"):
        return False, f"expected a burger/sandwich item, got {line.item_id!r}"
    if line.qty != 2:
        return False, f"expected qty=2, got {line.qty}"
    if "meal" not in line.option_ids:
        return False, f"expected 'meal' selected in option_ids, got {line.option_ids}"
    return True, "ok"


SCENARIOS: dict[str, tuple[list[str], callable]] = {
    "1_delivery_to_pickup": (
        [
            "أبغى توصيل على حي النرجس",
            "أبغى شكشوكة حجم كبير مع خبز تميس",
            "وبرجر دجاج كرسبي، خلها وجبة، خبز بريوش، بدون حار",
            "خلها استلام",
        ],
        check_1_delivery_to_pickup,
    ),
    "2_unavailable_after_branch_change": (
        [
            "أبغى توصيل على حي النرجس",
            "أبغى حمص باللحم حجم عادي بدون حار",
            "خلها توصيل على الروضة",
            "اكد الطلب",
        ],
        check_2_unavailable_after_branch_change,
    ),
    "3_remove_then_fresh_readback": (
        [
            "أبغى استلام من فرع الملقا",
            "أبغى بيتزا مارغريتا وسط عجينة كلاسيك بدون حار",
            "وشكشوكة حجم صغير خبز صاج",
            "كم المجموع؟",
            "شيل الشكشوكة",
            "اكد الطلب",
        ],
        check_3_remove_then_fresh_readback,
    ),
    "4_everything_in_one_sentence": (
        [
            "أبي توصيل للياسمين ٢ شاورما دجاج كبير",
            "خبز بريوش، وخلها وجبة، وبدون حار",
        ],
        check_4_everything_in_one_sentence,
    ),
    "5_quantity_correction": (
        [
            "أبغى استلام من فرع العليا",
            "أبغى ٢ حمص حجم عادي بدون حار",
            "لا لا، خلها ثلاثة مو اثنين",
        ],
        check_5_quantity_correction,
    ),
    "6_complaint_transfers": (
        [
            "أبغى توصيل على النرجس",
            "عندي شكوى، الطلب اللي طلبته قبل جاني ناقص وأبغى أتكلم مع احد",
        ],
        check_6_complaint_transfers,
    ),
    "7_idempotent_confirm": (
        [
            "أبغى استلام من فرع الملقا",
            "أبغى بيتزا مارغريتا وسط عجينة كلاسيك بدون حار",
            "جاهز للتأكيد، وش المجموع؟",
            "ايه",
            "ايه",
        ],
        check_7_idempotent_confirm,
    ),
    "8_code_switching_qty_and_meal": (
        [
            "أبي ٢ برجر large meal",
            "برجر لحم كلاسيك، خبز بريوش، بدون حار",
        ],
        check_8_code_switching_qty_and_meal,
    ),
}
