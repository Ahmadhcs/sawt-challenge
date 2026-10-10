import csv
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from rapidfuzz import fuzz

from .arabic import extract_keywords, normalize_ar

MENU_CSV_PATH = Path(__file__).parent.parent / "data" / "menu.csv"
BRANCH_IDS = ["ruh_olaya", "ruh_narjis", "ruh_malqa", "jed_rawdah"]
SEARCH_SCORE_THRESHOLD = 60
AMBIGUOUS_SCORE_MARGIN = 5


SIZE_GROUP_IDS = ("size", "portion")


@dataclass
class Option:
    option_id: str
    name_ar: str
    name_en: str
    price_delta_halalas: int


@dataclass
class OptionGroup:
    group_id: str
    name_ar: str
    required: bool
    min_select: int
    max_select: int
    options: dict[str, Option] = field(default_factory=dict)


@dataclass
class MenuItem:
    item_id: str
    name_ar: str
    name_en: str
    category_id: str
    category_ar: str
    base_price_halalas: int
    availability: dict[str, bool] = field(default_factory=dict)
    option_groups: dict[str, OptionGroup] = field(default_factory=dict)


def _to_halalas(sar_text: str) -> int:
    return round(float(sar_text) * 100)


@cache
def load_menu() -> dict[str, MenuItem]:
    items: dict[str, MenuItem] = {}

    with open(MENU_CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            item_id = row["item_id"]

            if item_id not in items:
                items[item_id] = MenuItem(
                    item_id=item_id,
                    name_ar=row["item_name_ar"],
                    name_en=row["item_name_en"],
                    category_id=row["category_id"],
                    category_ar=row["category_ar"],
                    base_price_halalas=_to_halalas(row["base_price_sar"]),
                    availability={
                        branch_id: row[f"available_{branch_id}"] == "true" for branch_id in BRANCH_IDS
                    },
                )
            item = items[item_id]

            group_id = row["option_group_id"]
            if group_id not in item.option_groups:
                item.option_groups[group_id] = OptionGroup(
                    group_id=group_id,
                    name_ar=row["option_group_name_ar"],
                    required=row["option_group_required"] == "true",
                    min_select=int(row["option_group_min_select"]),
                    max_select=int(row["option_group_max_select"]),
                )
            group = item.option_groups[group_id]

            group.options[row["option_id"]] = Option(
                option_id=row["option_id"],
                name_ar=row["option_name_ar"],
                name_en=row["option_name_en"],
                price_delta_halalas=_to_halalas(row["option_price_delta_sar"]),
            )

    return items


def get_item(item_id: str) -> MenuItem | None:
    return load_menu().get(item_id)


def list_categories() -> list[str]:
    seen: list[str] = []
    for item in load_menu().values():
        if item.category_id not in seen:
            seen.append(item.category_id)
    return seen


def list_category(category_id: str) -> list[MenuItem]:
    return [item for item in load_menu().values() if item.category_id == category_id]


def is_available(item_id: str, branch_id: str) -> bool:
    item = load_menu()[item_id]
    return item.availability.get(branch_id, False)


def item_price(item_id: str, size: str | None, option_ids: list[str]) -> int:
    item = load_menu()[item_id]
    total = item.base_price_halalas

    if size is not None:
        for group_id in SIZE_GROUP_IDS:
            group = item.option_groups.get(group_id)
            if group and size in group.options:
                total += group.options[size].price_delta_halalas
                break

    seen: set[str] = set()
    for option_id in option_ids:
        if option_id in seen:
            continue
        seen.add(option_id)
        for group in item.option_groups.values():
            if group.group_id in SIZE_GROUP_IDS:
                continue
            if option_id in group.options:
                total += group.options[option_id].price_delta_halalas
                break

    return total


@dataclass
class MenuSearchResult:
    item_id: str
    name_ar: str
    name_en: str
    category_id: str
    starting_price_halalas: int
    score: float
    available: bool | None
    detected_size: str | None
    detected_options: list[str]
    ambiguous: bool


def _starting_price_halalas(item: MenuItem) -> int:
    total = item.base_price_halalas
    for group in item.option_groups.values():
        if not group.required:
            continue
        deltas = [option.price_delta_halalas for option in group.options.values()]
        if deltas:
            total += min(deltas)
    return total


def _tokens(text: str) -> list[str]:
    return [t for t in text.split(" ") if t]


def _name_tokens(item: MenuItem) -> list[str]:
    return _tokens(normalize_ar(f"{item.name_ar} {item.name_en}"))


def _searchable_text(item: MenuItem) -> str:
    return normalize_ar(f"{item.name_ar} {item.name_en} {item.category_ar}")


def _token_coverage(query_tokens: list[str], target_tokens: list[str]) -> float:
    """Average, over each query token, of its best fuzz.ratio match against any
    target token. A single query token that fully matches one target token (a
    one-word query hitting a name token head-on) scores 100, not diluted by
    string length the way a whole-string ratio would be."""
    if not query_tokens or not target_tokens:
        return 0.0
    return sum(max(fuzz.ratio(q, t) for t in target_tokens) for q in query_tokens) / len(query_tokens)


def search_menu(query: str, branch_id: str | None = None, limit: int = 5) -> list[MenuSearchResult]:
    search_text, detected_size, detected_options = extract_keywords(normalize_ar(query))
    query_tokens = _tokens(search_text)
    name_match_tokens = [t for t in query_tokens if not t.isdigit()]

    scored = []
    for item in load_menu().values():
        name_score = _token_coverage(name_match_tokens, _name_tokens(item))

        if name_score < SEARCH_SCORE_THRESHOLD:
            continue

        tiebreak_score = fuzz.WRatio(search_text, _searchable_text(item)) if search_text else 0.0
        scored.append((name_score, tiebreak_score, item))

    scored.sort(key=lambda row: (-row[0], -row[1], row[2].item_id))

    ambiguous = len(scored) >= 2 and (scored[0][0] - scored[1][0]) <= AMBIGUOUS_SCORE_MARGIN

    results = []
    for name_score, _tiebreak, item in scored[:limit]:
        results.append(
            MenuSearchResult(
                item_id=item.item_id,
                name_ar=item.name_ar,
                name_en=item.name_en,
                category_id=item.category_id,
                starting_price_halalas=_starting_price_halalas(item),
                score=name_score,
                available=item.availability.get(branch_id) if branch_id else None,
                detected_size=detected_size,
                detected_options=detected_options,
                ambiguous=ambiguous,
            )
        )
    return results
