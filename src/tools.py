from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from rapidfuzz import fuzz

from .arabic import normalize_ar, tokens
from .order_state import ORDERS_JSON_PATH, OrderState, halalas_to_sar_str
from .restaurant_db import get_item, list_categories, list_category, load_menu, search_menu, starting_price_halalas

CATEGORY_SCORE_THRESHOLD = 75


@dataclass
class CallSession:
    order: OrderState
    transferred: bool = False
    transfer_reason: str | None = None
    consecutive_failures: int = 0
    orders_path: Path = ORDERS_JSON_PATH
    turn_number: int = 0


def llm_summary(order: OrderState) -> dict:
    full = order.summary()
    lines = [{k: v for k, v in line.items() if not k.endswith("_halalas")} for line in full["lines"]]
    top_level = {k: v for k, v in full.items() if not k.endswith("_halalas") and k != "lines"}
    return {**top_level, "lines": lines}


def _success_with_summary(order: OrderState, extra: dict | None = None) -> dict:
    response = {"ok": True, **(extra or {})}
    response.update(llm_summary(order))
    return response


def _find_category(text: str) -> str | None:
    category_ar_by_id: dict[str, str] = {}
    for item in load_menu().values():
        category_ar_by_id.setdefault(item.category_id, item.category_ar)

    query_tokens = tokens(normalize_ar(text))
    best_id = None
    best_score = 0.0
    for category_id, category_ar in category_ar_by_id.items():
        candidate_tokens = tokens(normalize_ar(category_ar))
        score = max((fuzz.ratio(q, c) for q in query_tokens for c in candidate_tokens), default=0.0)
        if score > best_score:
            best_score = score
            best_id = category_id

    return best_id if best_score >= CATEGORY_SCORE_THRESHOLD else None


class SearchMenuArgs(BaseModel):
    query: str


def _handle_search_menu(session: CallSession, args: SearchMenuArgs) -> dict:
    results = search_menu(args.query, branch_id=session.order.branch_id)
    return {
        "ok": True,
        "results": [
            {
                "item_id": r.item_id,
                "name_ar": r.name_ar,
                "starting_price_sar": halalas_to_sar_str(r.starting_price_halalas),
                "available": r.available,
                "detected_size": r.detected_size,
                "detected_options": r.detected_options,
                "ambiguous": r.ambiguous,
            }
            for r in results
        ],
    }


class ListCategoryArgs(BaseModel):
    category: str


def _handle_list_category(session: CallSession, args: ListCategoryArgs) -> dict:
    category_id = _find_category(args.category)
    if category_id is None:
        return {"ok": True, "matched": False, "categories": list_categories()}

    items = list_category(category_id)
    return {
        "ok": True,
        "matched": True,
        "category": category_id,
        "dishes": [
            {
                "item_id": item.item_id,
                "name_ar": item.name_ar,
                "starting_price_sar": halalas_to_sar_str(starting_price_halalas(item)),
            }
            for item in items
        ],
    }


class GetItemDetailsArgs(BaseModel):
    item_id: str


def _handle_get_item_details(session: CallSession, args: GetItemDetailsArgs) -> dict:
    item = get_item(args.item_id)
    if item is None:
        return {"ok": False, "error": f"no such item: {args.item_id}"}

    option_groups = [
        {
            "group_id": group.group_id,
            "name_ar": group.name_ar,
            "required": group.required,
            "min_select": group.min_select,
            "max_select": group.max_select,
            "options": [
                {
                    "option_id": option.option_id,
                    "name_ar": option.name_ar,
                    "price_delta_sar": halalas_to_sar_str(option.price_delta_halalas),
                }
                for option in group.options.values()
            ],
        }
        for group in item.option_groups.values()
    ]
    return {
        "ok": True,
        "item_id": item.item_id,
        "name_ar": item.name_ar,
        "starting_price_sar": halalas_to_sar_str(starting_price_halalas(item)),
        "option_groups": option_groups,
    }


class SetServiceTypeArgs(BaseModel):
    service_type: Literal["delivery", "pickup"]


def _handle_set_service_type(session: CallSession, args: SetServiceTypeArgs) -> dict:
    result = session.order.set_service_type(args.service_type)
    if result.error:
        return {"ok": False, "error": result.error}
    extra = {}
    if result.suggested_pickup_branch_id:
        extra["suggested_pickup_branch_id"] = result.suggested_pickup_branch_id
    return _success_with_summary(session.order, extra)


class SetLocationArgs(BaseModel):
    location_text: str


def _handle_set_location(session: CallSession, args: SetLocationArgs) -> dict:
    error = session.order.set_location(args.location_text)
    if error:
        return {"ok": False, "error": error}
    return _success_with_summary(session.order)


class SetPickupBranchArgs(BaseModel):
    branch_text: str


def _handle_set_pickup_branch(session: CallSession, args: SetPickupBranchArgs) -> dict:
    error = session.order.set_pickup_branch(args.branch_text)
    if error:
        return {"ok": False, "error": error}
    return _success_with_summary(session.order)


class AddItemArgs(BaseModel):
    item_id: str
    qty: int = Field(ge=1)
    size: str | None = None
    option_ids: list[str] = Field(default_factory=list)
    notes: str = ""


def _handle_add_item(session: CallSession, args: AddItemArgs) -> dict:
    error = session.order.add_line(args.item_id, args.qty, args.size, args.option_ids, args.notes)
    if error:
        return {"ok": False, "error": error}
    return _success_with_summary(session.order)


class UpdateItemArgs(BaseModel):
    line_id: str
    qty: int | None = Field(default=None, ge=1)
    size: str | None = None
    option_ids: list[str] | None = None
    notes: str | None = None


def _handle_update_item(session: CallSession, args: UpdateItemArgs) -> dict:
    error = session.order.update_line(args.line_id, args.qty, args.size, args.option_ids, args.notes)
    if error:
        return {"ok": False, "error": error}
    return _success_with_summary(session.order)


class RemoveItemArgs(BaseModel):
    line_id: str


def _handle_remove_item(session: CallSession, args: RemoveItemArgs) -> dict:
    error = session.order.remove_line(args.line_id)
    if error:
        return {"ok": False, "error": error}
    return _success_with_summary(session.order)


class GetOrderSummaryArgs(BaseModel):
    pass


def _handle_get_order_summary(session: CallSession, args: GetOrderSummaryArgs) -> dict:
    session.order.get_order_summary(session.turn_number)
    return _success_with_summary(session.order)


class ConfirmOrderArgs(BaseModel):
    pass


def _handle_confirm_order(session: CallSession, args: ConfirmOrderArgs) -> dict:
    result = session.order.confirm_order(session.turn_number, orders_path=session.orders_path)
    if result.error:
        return {"ok": False, "error": result.error}
    return _success_with_summary(session.order, {"order_id": result.order_id})


class TransferToHumanArgs(BaseModel):
    reason: str


def _handle_transfer_to_human(session: CallSession, args: TransferToHumanArgs) -> dict:
    session.transferred = True
    session.transfer_reason = args.reason
    return {"ok": True, "transferred": True, "reason": args.reason}


TOOL_DESCRIPTIONS: dict[str, str] = {
    "search_menu": "Search the menu by dish name. Pass only dish words, not filler like ابغى/ابي.",
    "list_category": "List dishes in one menu category by its Arabic name as the caller said it, e.g. حلويات.",
    "get_item_details": "Get a dish's option groups and valid option IDs before adding it to the order.",
    "set_service_type": "Set whether this order is delivery or pickup.",
    "set_location": "Set the delivery location from what the caller said.",
    "set_pickup_branch": "Set which branch the caller will pick up from.",
    "add_item": "Add one dish to the order with its quantity, size, and chosen options.",
    "update_item": "Change the quantity, size, options, or notes on an existing order line.",
    "remove_item": "Remove a line from the order.",
    "get_order_summary": "Read back the current order: items, fees, and total. Call this before confirming.",
    "confirm_order": "Confirm the order after the caller gives clear agreement to the read-back.",
    "transfer_to_human": "Transfer the call to a human agent, e.g. for a complaint or explicit request.",
}

TOOL_HANDLERS: dict[str, tuple[type[BaseModel], Callable]] = {
    "search_menu": (SearchMenuArgs, _handle_search_menu),
    "list_category": (ListCategoryArgs, _handle_list_category),
    "get_item_details": (GetItemDetailsArgs, _handle_get_item_details),
    "set_service_type": (SetServiceTypeArgs, _handle_set_service_type),
    "set_location": (SetLocationArgs, _handle_set_location),
    "set_pickup_branch": (SetPickupBranchArgs, _handle_set_pickup_branch),
    "add_item": (AddItemArgs, _handle_add_item),
    "update_item": (UpdateItemArgs, _handle_update_item),
    "remove_item": (RemoveItemArgs, _handle_remove_item),
    "get_order_summary": (GetOrderSummaryArgs, _handle_get_order_summary),
    "confirm_order": (ConfirmOrderArgs, _handle_confirm_order),
    "transfer_to_human": (TransferToHumanArgs, _handle_transfer_to_human),
}


def run_tool(session: CallSession, name: str, args: dict) -> dict:
    entry = TOOL_HANDLERS.get(name)
    if entry is None:
        return {"ok": False, "error": f"unknown tool: {name}"}

    model_cls, handler = entry
    try:
        parsed_args = model_cls(**args)
    except ValidationError as e:
        messages = [err["msg"] for err in e.errors()]
        return {"ok": False, "error": "; ".join(messages)}

    try:
        return handler(session, parsed_args)
    except Exception as e:
        return {"ok": False, "error": f"internal error: {e}"}


def _tool_schema(name: str, model_cls: type[BaseModel]) -> dict:
    schema = model_cls.model_json_schema()
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": TOOL_DESCRIPTIONS[name],
            "parameters": schema,
        },
    }


def get_openai_tool_schemas() -> list[dict]:
    return [_tool_schema(name, model_cls) for name, (model_cls, _handler) in TOOL_HANDLERS.items()]
