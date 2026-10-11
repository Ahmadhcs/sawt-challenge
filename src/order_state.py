import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from .locations import find_branch, find_zone, load_branches, load_zones
from .restaurant_db import SIZE_GROUP_IDS, MenuItem, get_item, is_available, item_price

ORDERS_JSON_PATH = Path(__file__).parent.parent / "orders.json"


def halalas_to_sar_str(halalas: int) -> str:
    sign = "-" if halalas < 0 else ""
    halalas = abs(halalas)
    return f"{sign}{halalas // 100}.{halalas % 100:02d}"


@dataclass
class ConfirmResult:
    order_id: str | None
    error: str | None


@dataclass
class ServiceTypeResult:
    error: str | None
    suggested_pickup_branch_id: str | None = None


@dataclass
class CartLine:
    line_id: str
    item_id: str
    qty: int
    size: str | None
    option_ids: list[str]
    notes: str


@dataclass
class OrderState:
    # inputs
    service_type: str | None = None
    zone_id: str | None = None
    pickup_branch_id: str | None = None
    lines: list[CartLine] = field(default_factory=list)

    # derived - rebuilt from scratch by recalculate(), never hand-edited
    branch_id: str | None = None
    delivery_fee_halalas: int = 0
    eta_minutes: int | None = None
    line_prices_halalas: dict[str, int] = field(default_factory=dict)
    unavailable_line_ids: list[str] = field(default_factory=list)
    subtotal_halalas: int = 0
    total_halalas: int = 0

    # bookkeeping
    version: int = 0
    readback_version: int | None = None
    readback_turn: int | None = None
    order_id: str | None = None
    status: str = "building"
    next_line_number: int = 0

    def recalculate(self) -> None:
        if self.service_type == "pickup" and self.pickup_branch_id:
            self.branch_id = self.pickup_branch_id
            self.delivery_fee_halalas = 0
            branch = load_branches().get(self.pickup_branch_id)
            self.eta_minutes = branch.pickup_prep_minutes if branch else None
        elif self.service_type == "delivery" and self.zone_id:
            zone = next((z for z in load_zones() if z.zone_id == self.zone_id), None)
            if zone:
                self.branch_id = zone.branch_id
                self.delivery_fee_halalas = zone.delivery_fee_halalas
                self.eta_minutes = zone.eta_minutes
            else:
                self.branch_id = None
                self.delivery_fee_halalas = 0
                self.eta_minutes = None
        else:
            self.branch_id = None
            self.delivery_fee_halalas = 0
            self.eta_minutes = None

        self.line_prices_halalas = {}
        self.unavailable_line_ids = []
        for line in self.lines:
            self.line_prices_halalas[line.line_id] = item_price(line.item_id, line.size, line.option_ids) * line.qty
            if self.branch_id is not None and not is_available(line.item_id, self.branch_id):
                self.unavailable_line_ids.append(line.line_id)

        self.subtotal_halalas = sum(self.line_prices_halalas.values())
        self.total_halalas = self.subtotal_halalas + self.delivery_fee_halalas

    def _confirmed_guard(self) -> str | None:
        if self.status == "confirmed":
            return "order already confirmed, no changes allowed"
        return None

    def set_service_type(self, service_type: str) -> ServiceTypeResult:
        blocked = self._confirmed_guard()
        if blocked:
            return ServiceTypeResult(error=blocked)
        if service_type not in ("delivery", "pickup"):
            return ServiceTypeResult(error=f"invalid service_type: {service_type}")

        suggested_pickup_branch_id = None
        if service_type == "pickup" and self.service_type == "delivery" and self.zone_id:
            zone = next((z for z in load_zones() if z.zone_id == self.zone_id), None)
            if zone:
                suggested_pickup_branch_id = zone.branch_id

        self.service_type = service_type
        if service_type == "pickup":
            self.zone_id = None
        else:
            self.pickup_branch_id = None

        self.version += 1
        self.recalculate()
        return ServiceTypeResult(error=None, suggested_pickup_branch_id=suggested_pickup_branch_id)

    def set_location(self, location_text: str) -> str | None:
        blocked = self._confirmed_guard()
        if blocked:
            return blocked
        zone = find_zone(location_text)
        if zone is None:
            return f"we don't deliver to '{location_text}' - would you like pickup instead?"

        self.service_type = "delivery"
        self.zone_id = zone.zone_id
        self.pickup_branch_id = None

        self.version += 1
        self.recalculate()
        return None

    def set_pickup_branch(self, text: str) -> str | None:
        blocked = self._confirmed_guard()
        if blocked:
            return blocked
        branch = find_branch(text)
        if branch is None:
            return f"couldn't find a branch matching '{text}'"

        self.service_type = "pickup"
        self.pickup_branch_id = branch.branch_id
        self.zone_id = None

        self.version += 1
        self.recalculate()
        return None

    def add_line(
        self, item_id: str, qty: int, size: str | None = None, option_ids: list[str] | None = None, notes: str = ""
    ) -> str | None:
        blocked = self._confirmed_guard()
        if blocked:
            return blocked
        option_ids = option_ids or []
        item = get_item(item_id)
        if item is None:
            return f"no such item: {item_id}"
        if not isinstance(qty, int) or qty < 1:
            return "qty must be a positive integer"

        error = _validate_selection(item, size, option_ids)
        if error:
            return error

        self.next_line_number += 1
        self.lines.append(
            CartLine(
                line_id=f"line_{self.next_line_number}",
                item_id=item_id,
                qty=qty,
                size=size,
                option_ids=list(option_ids),
                notes=notes,
            )
        )
        self.version += 1
        self.recalculate()
        return None

    def update_line(
        self,
        line_id: str,
        qty: int | None = None,
        size: str | None = None,
        option_ids: list[str] | None = None,
        notes: str | None = None,
    ) -> str | None:
        blocked = self._confirmed_guard()
        if blocked:
            return blocked
        line = next((l for l in self.lines if l.line_id == line_id), None)
        if line is None:
            return f"no such line: {line_id}"

        new_qty = line.qty if qty is None else qty
        new_size = line.size if size is None else size
        new_option_ids = line.option_ids if option_ids is None else option_ids
        new_notes = line.notes if notes is None else notes

        if not isinstance(new_qty, int) or new_qty < 1:
            return "qty must be a positive integer"

        item = get_item(line.item_id)
        if item is None:
            return f"no such item: {line.item_id}"

        error = _validate_selection(item, new_size, new_option_ids)
        if error:
            return error

        line.qty = new_qty
        line.size = new_size
        line.option_ids = list(new_option_ids)
        line.notes = new_notes

        self.version += 1
        self.recalculate()
        return None

    def remove_line(self, line_id: str) -> str | None:
        blocked = self._confirmed_guard()
        if blocked:
            return blocked
        line = next((l for l in self.lines if l.line_id == line_id), None)
        if line is None:
            return f"no such line: {line_id}"

        self.lines.remove(line)
        self.version += 1
        self.recalculate()
        return None

    def summary(self) -> dict:
        lines_summary = []
        for line in self.lines:
            item = get_item(line.item_id)
            lines_summary.append(
                {
                    "line_id": line.line_id,
                    "item_id": line.item_id,
                    "name_ar": item.name_ar if item else None,
                    "name_en": item.name_en if item else None,
                    "qty": line.qty,
                    "size": line.size,
                    "option_ids": line.option_ids,
                    "notes": line.notes,
                    "price_halalas": self.line_prices_halalas.get(line.line_id, 0),
                    "line_total_sar": halalas_to_sar_str(self.line_prices_halalas.get(line.line_id, 0)),
                    "unavailable": line.line_id in self.unavailable_line_ids,
                }
            )

        return {
            "order_id": self.order_id,
            "status": self.status,
            "service_type": self.service_type,
            "zone_id": self.zone_id,
            "pickup_branch_id": self.pickup_branch_id,
            "branch_id": self.branch_id,
            "lines": lines_summary,
            "delivery_fee_halalas": self.delivery_fee_halalas,
            "delivery_fee_sar": halalas_to_sar_str(self.delivery_fee_halalas),
            "eta_minutes": self.eta_minutes,
            "subtotal_halalas": self.subtotal_halalas,
            "subtotal_sar": halalas_to_sar_str(self.subtotal_halalas),
            "total_halalas": self.total_halalas,
            "total_sar": halalas_to_sar_str(self.total_halalas),
            "version": self.version,
            "readback_version": self.readback_version,
        }

    def get_order_summary(self, turn_number: int) -> dict:
        self.readback_version = self.version
        self.readback_turn = turn_number
        return self.summary()

    def confirm_order(self, turn_number: int, orders_path: Path | str = ORDERS_JSON_PATH) -> ConfirmResult:
        if self.status == "confirmed":
            return ConfirmResult(order_id=self.order_id, error=None)

        if self.readback_turn is None or self.readback_turn == turn_number:
            return ConfirmResult(
                order_id=None,
                error="read the order back to the caller and wait for their answer before confirming",
            )
        if self.readback_version is None or self.readback_version != self.version:
            return ConfirmResult(order_id=None, error="please read back the order before confirming")
        if self.service_type is None:
            return ConfirmResult(order_id=None, error="service type is not set")
        if self.service_type == "delivery" and self.zone_id is None:
            return ConfirmResult(order_id=None, error="no delivery location set")
        if self.service_type == "pickup" and self.pickup_branch_id is None:
            return ConfirmResult(order_id=None, error="no pickup branch set")
        if not self.lines:
            return ConfirmResult(order_id=None, error="cart is empty")
        if self.unavailable_line_ids:
            return ConfirmResult(order_id=None, error="some items are unavailable, please update the cart")

        self.status = "confirmed"
        order_id = self._persist_confirmed_order(Path(orders_path))
        return ConfirmResult(order_id=order_id, error=None)

    def _persist_confirmed_order(self, orders_path: Path) -> str:
        records = []
        if orders_path.exists():
            with open(orders_path, encoding="utf-8") as f:
                records = json.load(f)

        existing_ids = {record.get("order_id") for record in records}
        order_id = f"{random.randint(100000, 999999)}"
        while order_id in existing_ids:
            order_id = f"{random.randint(100000, 999999)}"

        self.order_id = order_id
        records.append(self.summary())

        with open(orders_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        return order_id


def _validate_selection(item: MenuItem, size: str | None, option_ids: list[str]) -> str | None:
    size_group = None
    for group_id in SIZE_GROUP_IDS:
        if group_id in item.option_groups:
            size_group = item.option_groups[group_id]
            break

    if size_group:
        if size is None:
            return f"size is required for {item.name_en}"
        if size not in size_group.options:
            return f"'{size}' is not a valid size for {item.name_en}"
    elif size is not None:
        return f"{item.name_en} has no size options"

    for group in item.option_groups.values():
        if group.group_id in SIZE_GROUP_IDS:
            continue
        selected = [o for o in option_ids if o in group.options]
        if len(selected) < group.min_select:
            return f"'{group.name_ar}' requires at least {group.min_select} selection(s) for {item.name_en}"
        if len(selected) > group.max_select:
            return f"too many selections for '{group.name_ar}' on {item.name_en}"

    known_option_ids = {option_id for group in item.option_groups.values() for option_id in group.options}
    unknown = [o for o in option_ids if o not in known_option_ids]
    if unknown:
        return f"unknown option(s) {unknown} for {item.name_en}"

    return None
