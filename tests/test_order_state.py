import json

from src.order_state import OrderState, halalas_to_sar_str


def test_add_line_computes_total_with_size_options_qty():
    order = OrderState()
    error = order.add_line(
        "pizza_flatbread_01", qty=2, size="large", option_ids=["stuffed", "hot", "cheese", "mushroom"]
    )
    assert error is None
    assert order.version == 1
    assert len(order.lines) == 1

    line_id = order.lines[0].line_id
    assert order.line_prices_halalas[line_id] == 14000
    assert order.subtotal_halalas == 14000
    assert order.total_halalas == 14000


def test_add_line_rejects_missing_required_size():
    order = OrderState()
    error = order.add_line("pizza_flatbread_01", qty=1, size=None, option_ids=["classic", "not_spicy"])
    assert error is not None
    assert order.version == 0
    assert order.lines == []


def test_add_line_rejects_invalid_size():
    order = OrderState()
    error = order.add_line("pizza_flatbread_01", qty=1, size="extra_large", option_ids=["classic", "not_spicy"])
    assert error is not None
    assert order.version == 0
    assert order.lines == []


def test_add_line_rejects_missing_required_option_group():
    order = OrderState()
    error = order.add_line("pizza_flatbread_01", qty=1, size="small", option_ids=["classic"])
    assert error is not None
    assert order.version == 0
    assert order.lines == []


def test_add_line_rejects_too_many_selections():
    order = OrderState()
    error = order.add_line(
        "breakfast_01",
        qty=1,
        size="regular",
        option_ids=["tamees", "cheese", "honey", "cream", "eggs"],
    )
    assert error is not None
    assert order.version == 0
    assert order.lines == []


def test_add_line_rejects_unknown_option():
    order = OrderState()
    error = order.add_line("breakfast_01", qty=1, size="regular", option_ids=["tamees", "not_a_real_option"])
    assert error is not None
    assert order.version == 0
    assert order.lines == []


def test_add_line_rejects_unknown_item():
    order = OrderState()
    error = order.add_line("not_a_real_item", qty=1)
    assert error is not None
    assert order.version == 0
    assert order.lines == []


def test_add_line_rejects_bad_qty():
    order = OrderState()
    error = order.add_line("breakfast_01", qty=0, size="regular", option_ids=["tamees"])
    assert error is not None
    assert order.version == 0
    assert order.lines == []


def test_update_line_changes_qty_and_recalculates():
    order = OrderState()
    order.add_line("breakfast_01", qty=1, size="regular", option_ids=["tamees"])
    line_id = order.lines[0].line_id
    version_before = order.version

    error = order.update_line(line_id, qty=3)
    assert error is None
    assert order.version == version_before + 1
    assert order.lines[0].qty == 3
    assert order.line_prices_halalas[line_id] == 2200 * 3
    assert order.total_halalas == 2200 * 3


def test_update_line_rejects_invalid_change_and_leaves_state_unchanged():
    order = OrderState()
    order.add_line("breakfast_01", qty=1, size="regular", option_ids=["tamees"])
    line_id = order.lines[0].line_id
    version_before = order.version
    total_before = order.total_halalas

    error = order.update_line(line_id, size="not_a_real_size")
    assert error is not None
    assert order.version == version_before
    assert order.lines[0].size == "regular"
    assert order.total_halalas == total_before


def test_update_line_unknown_line_id():
    order = OrderState()
    error = order.update_line("not_a_real_line", qty=2)
    assert error is not None
    assert order.version == 0


def test_remove_line_recalculates_total():
    order = OrderState()
    assert order.add_line("breakfast_01", qty=1, size="regular", option_ids=["tamees"]) is None
    assert order.add_line("appetizers_01", qty=1, size="regular", option_ids=["not_spicy"]) is None
    assert len(order.lines) == 2
    version_before = order.version

    first_line_id = order.lines[0].line_id
    error = order.remove_line(first_line_id)
    assert error is None
    assert order.version == version_before + 1
    assert len(order.lines) == 1
    assert order.total_halalas == order.line_prices_halalas[order.lines[0].line_id]


def test_remove_line_unknown_line_id_leaves_state_unchanged():
    order = OrderState()
    order.add_line("breakfast_01", qty=1, size="regular", option_ids=["tamees"])
    version_before = order.version
    lines_before = list(order.lines)

    error = order.remove_line("not_a_real_line")
    assert error is not None
    assert order.version == version_before
    assert order.lines == lines_before


def test_summary_shape():
    order = OrderState()
    order.add_line("breakfast_01", qty=1, size="regular", option_ids=["tamees"])
    summary = order.summary()
    assert summary["status"] == "building"
    assert summary["total_halalas"] == 2200
    assert len(summary["lines"]) == 1
    assert summary["lines"][0]["name_en"] == "Shakshuka"
    assert summary["lines"][0]["unavailable"] is False


def test_delivery_to_pickup_sets_fee_zero():
    order = OrderState()
    assert order.set_location("حي النرجس") is None
    assert order.delivery_fee_halalas == 500
    version_before = order.version

    assert order.set_pickup_branch("الملقا") is None
    assert order.version == version_before + 1
    assert order.delivery_fee_halalas == 0
    assert order.branch_id == "ruh_malqa"
    assert order.eta_minutes == 18  # ruh_malqa's pickup_prep_minutes


def test_riyadh_to_jeddah_flags_unavailable_item_then_clears_on_switch_back():
    order = OrderState()
    assert order.set_location("النرجس") is None
    assert order.branch_id == "ruh_narjis"

    line_error = order.add_line("appetizers_02", qty=1, size="regular", option_ids=["not_spicy"])
    assert line_error is None
    line_id = order.lines[0].line_id
    assert order.unavailable_line_ids == []

    assert order.set_location("الزهراء") is None
    assert order.branch_id == "jed_rawdah"
    assert line_id in order.unavailable_line_ids
    assert order.lines[0].line_id == line_id

    assert order.set_location("النرجس") is None
    assert order.branch_id == "ruh_narjis"
    assert order.unavailable_line_ids == []


def test_set_location_out_of_zone_leaves_state_unchanged():
    order = OrderState()
    assert order.set_location("حي النرجس") is None
    version_before = order.version
    branch_before = order.branch_id

    error = order.set_location("الخبر")
    assert error is not None
    assert "pickup" in error
    assert order.version == version_before
    assert order.branch_id == branch_before


def test_every_location_change_bumps_version():
    order = OrderState()
    v0 = order.version
    order.set_service_type("delivery")
    v1 = order.version
    order.set_location("النرجس")
    v2 = order.version
    order.set_pickup_branch("الملقا")
    v3 = order.version

    assert v1 == v0 + 1
    assert v2 == v1 + 1
    assert v3 == v2 + 1


def test_no_branch_yet_availability_unknown():
    order = OrderState()
    order.add_line("appetizers_02", qty=1, size="regular", option_ids=["not_spicy"])
    assert order.branch_id is None
    assert order.unavailable_line_ids == []


def _ready_order() -> OrderState:
    order = OrderState()
    order.set_location("النرجس")
    order.add_line("appetizers_02", qty=1, size="regular", option_ids=["not_spicy"])
    return order


def test_confirm_without_readback_fails(tmp_path):
    order = _ready_order()
    result = order.confirm_order(orders_path=tmp_path / "orders.json")
    assert result.order_id is None
    assert result.error is not None
    assert order.status == "building"


def test_change_after_readback_requires_new_readback(tmp_path):
    order = _ready_order()
    order.get_order_summary()
    order.add_line("appetizers_01", qty=1, size="regular", option_ids=["not_spicy"])

    result = order.confirm_order(orders_path=tmp_path / "orders.json")
    assert result.order_id is None
    assert result.error is not None

    order.get_order_summary()
    result = order.confirm_order(orders_path=tmp_path / "orders.json")
    assert result.error is None
    assert result.order_id is not None


def test_double_confirm_same_id_and_one_record(tmp_path):
    orders_path = tmp_path / "orders.json"
    order = _ready_order()
    order.get_order_summary()

    first = order.confirm_order(orders_path=orders_path)
    assert first.error is None
    assert first.order_id is not None

    second = order.confirm_order(orders_path=orders_path)
    assert second.error is None
    assert second.order_id == first.order_id

    with open(orders_path, encoding="utf-8") as f:
        records = json.load(f)
    assert len(records) == 1
    assert records[0]["order_id"] == first.order_id


def test_confirm_blocked_when_item_unavailable(tmp_path):
    order = OrderState()
    order.set_location("النرجس")
    order.add_line("appetizers_02", qty=1, size="regular", option_ids=["not_spicy"])
    order.set_location("الزهراء")
    order.get_order_summary()

    result = order.confirm_order(orders_path=tmp_path / "orders.json")
    assert result.order_id is None
    assert "unavailable" in result.error
    assert order.status == "building"


def test_changes_after_confirmation_rejected(tmp_path):
    order = _ready_order()
    order.get_order_summary()
    order.confirm_order(orders_path=tmp_path / "orders.json")
    assert order.status == "confirmed"
    version_before = order.version

    error = order.add_line("appetizers_01", qty=1, size="regular", option_ids=["not_spicy"])
    assert error is not None
    assert order.version == version_before
    assert len(order.lines) == 1


def test_halalas_to_sar_str_formatting():
    assert halalas_to_sar_str(8750) == "87.50"
    assert halalas_to_sar_str(2200) == "22.00"
    assert halalas_to_sar_str(5) == "0.05"
    assert halalas_to_sar_str(0) == "0.00"


def test_summary_includes_sar_display_strings():
    order = OrderState()
    order.set_location("النرجس")  # delivery_fee_halalas = 500 -> "5.00"
    order.add_line("breakfast_01", qty=1, size="regular", option_ids=["tamees"])
    summary = order.summary()

    assert summary["lines"][0]["line_total_sar"] == "22.00"
    assert summary["delivery_fee_sar"] == "5.00"
    assert summary["subtotal_sar"] == "22.00"
    assert summary["total_sar"] == "27.00"


def test_set_service_type_delivery_to_pickup_suggests_previous_branch():
    order = OrderState()
    order.set_location("النرجس")
    result = order.set_service_type("pickup")

    assert result.error is None
    assert result.suggested_pickup_branch_id == "ruh_narjis"
    assert order.pickup_branch_id is None
    assert order.zone_id is None


def test_set_service_type_no_suggestion_without_prior_zone():
    order = OrderState()
    result = order.set_service_type("pickup")
    assert result.error is None
    assert result.suggested_pickup_branch_id is None
