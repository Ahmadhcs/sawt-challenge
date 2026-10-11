from src.order_state import OrderState
from src.tools import CallSession, get_openai_tool_schemas, run_tool


def _new_session() -> CallSession:
    return CallSession(order=OrderState())


def _assert_no_halalas(value) -> None:
    if isinstance(value, dict):
        for key, v in value.items():
            assert not key.endswith("_halalas"), f"found halalas field: {key}"
            _assert_no_halalas(v)
    elif isinstance(value, list):
        for v in value:
            _assert_no_halalas(v)


def test_search_menu_tool():
    session = _new_session()
    result = run_tool(session, "search_menu", {"query": "بيتزا مارغريتا"})
    assert result["ok"] is True
    assert result["results"][0]["item_id"] == "pizza_flatbread_01"
    assert result["results"][0]["starting_price_sar"] == "32.00"
    _assert_no_halalas(result)


def test_list_category_tool_match():
    session = _new_session()
    result = run_tool(session, "list_category", {"category": "حلويات"})
    assert result["ok"] is True
    assert result["matched"] is True
    assert result["category"] == "desserts"
    assert any(d["item_id"] == "desserts_01" for d in result["dishes"])
    _assert_no_halalas(result)


def test_list_category_tool_no_match_returns_category_list():
    session = _new_session()
    result = run_tool(session, "list_category", {"category": "xyz123"})
    assert result["ok"] is True
    assert result["matched"] is False
    assert "desserts" in result["categories"]


def test_get_item_details_tool():
    session = _new_session()
    result = run_tool(session, "get_item_details", {"item_id": "breakfast_01"})
    assert result["ok"] is True
    group_ids = [g["group_id"] for g in result["option_groups"]]
    assert "portion" in group_ids
    portion = next(g for g in result["option_groups"] if g["group_id"] == "portion")
    assert portion["required"] is True
    assert any(o["option_id"] == "large" and o["price_delta_sar"] == "8.00" for o in portion["options"])
    _assert_no_halalas(result)


def test_get_item_details_tool_unknown_item():
    session = _new_session()
    result = run_tool(session, "get_item_details", {"item_id": "not_a_real_item"})
    assert result["ok"] is False
    assert "error" in result


def test_set_service_type_tool():
    session = _new_session()
    result = run_tool(session, "set_service_type", {"service_type": "pickup"})
    assert result["ok"] is True
    assert session.order.service_type == "pickup"
    _assert_no_halalas(result)


def test_set_service_type_tool_invalid_value():
    session = _new_session()
    result = run_tool(session, "set_service_type", {"service_type": "teleport"})
    assert result["ok"] is False


def test_set_service_type_tool_suggests_pickup_branch():
    session = _new_session()
    run_tool(session, "set_location", {"location_text": "النرجس"})
    result = run_tool(session, "set_service_type", {"service_type": "pickup"})
    assert result["ok"] is True
    assert result["suggested_pickup_branch_id"] == "ruh_narjis"
    assert session.order.pickup_branch_id is None


def test_set_location_tool():
    session = _new_session()
    result = run_tool(session, "set_location", {"location_text": "النرجس"})
    assert result["ok"] is True
    assert result["branch_id"] == "ruh_narjis"
    _assert_no_halalas(result)


def test_set_location_tool_out_of_zone_error():
    session = _new_session()
    result = run_tool(session, "set_location", {"location_text": "الخبر"})
    assert result["ok"] is False
    assert "pickup" in result["error"]


def test_set_pickup_branch_tool():
    session = _new_session()
    result = run_tool(session, "set_pickup_branch", {"branch_text": "الملقا"})
    assert result["ok"] is True
    assert result["branch_id"] == "ruh_malqa"


def test_add_item_tool():
    session = _new_session()
    result = run_tool(
        session, "add_item", {"item_id": "breakfast_01", "qty": 1, "size": "regular", "option_ids": ["tamees"]}
    )
    assert result["ok"] is True
    assert result["lines"][0]["line_total_sar"] == "22.00"
    _assert_no_halalas(result)


def test_add_item_tool_order_state_validation_error():
    session = _new_session()
    result = run_tool(session, "add_item", {"item_id": "breakfast_01", "qty": 1})  # missing required size
    assert result["ok"] is False
    assert "error" in result


def test_add_item_tool_pydantic_validation_error():
    session = _new_session()
    result = run_tool(session, "add_item", {"item_id": "breakfast_01", "qty": 0})
    assert result["ok"] is False
    assert "error" in result


def test_update_item_tool():
    session = _new_session()
    run_tool(session, "add_item", {"item_id": "breakfast_01", "qty": 1, "size": "regular", "option_ids": ["tamees"]})
    line_id = session.order.lines[0].line_id
    result = run_tool(session, "update_item", {"line_id": line_id, "qty": 3})
    assert result["ok"] is True
    assert result["lines"][0]["qty"] == 3


def test_update_item_tool_unknown_line():
    session = _new_session()
    result = run_tool(session, "update_item", {"line_id": "not_a_real_line", "qty": 2})
    assert result["ok"] is False


def test_remove_item_tool():
    session = _new_session()
    run_tool(session, "add_item", {"item_id": "breakfast_01", "qty": 1, "size": "regular", "option_ids": ["tamees"]})
    line_id = session.order.lines[0].line_id
    result = run_tool(session, "remove_item", {"line_id": line_id})
    assert result["ok"] is True
    assert result["lines"] == []


def test_get_order_summary_tool_records_readback():
    session = _new_session()
    run_tool(session, "add_item", {"item_id": "breakfast_01", "qty": 1, "size": "regular", "option_ids": ["tamees"]})
    result = run_tool(session, "get_order_summary", {})
    assert result["ok"] is True
    assert session.order.readback_version == session.order.version
    _assert_no_halalas(result)


def test_confirm_order_tool_full_flow():
    session = _new_session()
    run_tool(session, "set_location", {"location_text": "النرجس"})
    run_tool(session, "add_item", {"item_id": "breakfast_01", "qty": 1, "size": "regular", "option_ids": ["tamees"]})
    run_tool(session, "get_order_summary", {})

    result = run_tool(session, "confirm_order", {})
    assert result["ok"] is True
    assert result["order_id"] is not None
    assert session.order.status == "confirmed"
    _assert_no_halalas(result)


def test_confirm_order_tool_without_readback_fails():
    session = _new_session()
    run_tool(session, "set_location", {"location_text": "النرجس"})
    run_tool(session, "add_item", {"item_id": "breakfast_01", "qty": 1, "size": "regular", "option_ids": ["tamees"]})

    result = run_tool(session, "confirm_order", {})
    assert result["ok"] is False


def test_transfer_to_human_tool():
    session = _new_session()
    result = run_tool(session, "transfer_to_human", {"reason": "complaint about last order"})
    assert result["ok"] is True
    assert session.transferred is True
    assert session.transfer_reason == "complaint about last order"


def test_run_tool_unknown_tool_name():
    session = _new_session()
    result = run_tool(session, "not_a_real_tool", {})
    assert result["ok"] is False
    assert "error" in result


def test_run_tool_never_raises_on_malformed_args():
    session = _new_session()
    result = run_tool(session, "add_item", {"item_id": 12345, "qty": "not a number"})
    assert result["ok"] is False
    assert "error" in result


def test_get_openai_tool_schemas_covers_all_tools():
    schemas = get_openai_tool_schemas()
    names = {s["function"]["name"] for s in schemas}
    assert names == {
        "search_menu",
        "list_category",
        "get_item_details",
        "set_service_type",
        "set_location",
        "set_pickup_branch",
        "add_item",
        "update_item",
        "remove_item",
        "get_order_summary",
        "confirm_order",
        "transfer_to_human",
    }
    for schema in schemas:
        assert schema["type"] == "function"
        assert schema["function"]["description"]
        assert schema["function"]["parameters"]["type"] == "object"
