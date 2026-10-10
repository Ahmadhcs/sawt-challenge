import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from rapidfuzz import fuzz

from .arabic import normalize_ar, tokens

BRANCHES_JSON_PATH = Path(__file__).parent.parent / "data" / "branches.json"
ZONES_JSON_PATH = Path(__file__).parent.parent / "data" / "zones.json"
LOCATION_SCORE_THRESHOLD = 75


@dataclass
class Branch:
    branch_id: str
    name_ar: str
    name_en: str
    city_ar: str
    city_en: str
    pickup_prep_minutes: int


@dataclass
class Zone:
    zone_id: str
    name_ar: str
    aliases: list[str]
    branch_id: str
    delivery_fee_halalas: int
    eta_minutes: int


@cache
def load_branches() -> dict[str, Branch]:
    with open(BRANCHES_JSON_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    return {row["branch_id"]: Branch(**row) for row in rows}


@cache
def load_zones() -> list[Zone]:
    with open(ZONES_JSON_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    return [Zone(**row) for row in rows]


def _best_location_match_score(location_text: str, candidates: list[str]) -> float:
    query_tokens = tokens(normalize_ar(location_text))
    if not query_tokens:
        return 0.0

    best = 0.0
    for candidate in candidates:
        candidate_tokens = tokens(normalize_ar(candidate))
        for q in query_tokens:
            for c in candidate_tokens:
                best = max(best, fuzz.ratio(q, c))
    return best


def find_zone(location_text: str) -> Zone | None:
    best_zone = None
    best_score = 0.0
    for zone in load_zones():
        score = _best_location_match_score(location_text, [zone.name_ar, *zone.aliases])
        if score > best_score:
            best_score = score
            best_zone = zone

    return best_zone if best_score >= LOCATION_SCORE_THRESHOLD else None


def find_branch(text: str) -> Branch | None:
    best_branch = None
    best_score = 0.0
    for branch in load_branches().values():
        score = _best_location_match_score(text, [branch.name_ar, branch.name_en, branch.city_ar, branch.city_en])
        if score > best_score:
            best_score = score
            best_branch = branch

    if best_score >= LOCATION_SCORE_THRESHOLD:
        return best_branch

    zone = find_zone(text)
    return load_branches().get(zone.branch_id) if zone else None
