from src.arabic import normalize_ar
from src.restaurant_db import (
    _starting_price_halalas,
    get_item,
    is_available,
    item_price,
    list_categories,
    list_category,
    load_menu,
    search_menu,
)


def test_loads_144_items():
    menu = load_menu()
    assert len(menu) == 144


def test_loads_12_categories():
    assert len(list_categories()) == 12


def test_known_item_has_expected_sizes_and_options():
    item = get_item("breakfast_01")
    assert item is not None
    assert item.name_en == "Shakshuka"
    assert item.base_price_halalas == 2200

    portion = item.option_groups["portion"]
    assert portion.required is True
    assert portion.min_select == 1
    assert portion.max_select == 1
    assert portion.options["regular"].price_delta_halalas == 0
    assert portion.options["large"].price_delta_halalas == 800

    extras = item.option_groups["extras"]
    assert extras.required is False
    assert extras.max_select == 3
    assert extras.options["cheese"].price_delta_halalas == 400


def test_availability_per_branch():
    assert is_available("breakfast_01", "ruh_olaya") is False
    assert is_available("breakfast_01", "ruh_narjis") is True
    assert is_available("breakfast_01", "ruh_malqa") is True
    assert is_available("breakfast_01", "jed_rawdah") is True


def test_item_price_with_size_and_options():
    price = item_price("breakfast_01", size="large", option_ids=["cheese"])
    assert price == 3400


def test_item_price_base_only():
    price = item_price("breakfast_01", size=None, option_ids=[])
    assert price == 2200


def test_get_item_missing_returns_none():
    assert get_item("does_not_exist") is None


def test_search_handles_spelling_variant():
    results = search_menu("شاورمه")
    assert results[0].item_id in ("sandwiches_07", "sandwiches_08")


def test_search_normalizes_arabic_digits():
    assert normalize_ar("بيتزا ٢") == "بيتزا 2"
    results = search_menu("بيتزا ٢")
    assert any(r.category_id == "pizza_flatbread" for r in results)


def test_search_handles_code_switching():
    results = search_menu("ابغى برجر large meal")
    assert any(r.item_id == "sandwiches_01" for r in results)


def test_search_handles_typo():
    results = search_menu("بتزا مارغريتا")
    assert results[0].item_id == "pizza_flatbread_01"


def test_search_no_result_below_threshold():
    assert search_menu("qwertyzzz nonsense") == []


def test_search_branch_filtering():
    at_olaya = search_menu("شكشوكة", branch_id="ruh_olaya")
    at_narjis = search_menu("شكشوكة", branch_id="ruh_narjis")

    assert at_olaya[0].item_id == "breakfast_01"
    assert at_olaya[0].available is False
    assert at_narjis[0].available is True


def test_search_detects_size_and_option_hints():
    results = search_menu("ابغى برجر large meal")
    assert results[0].item_id.startswith("sandwiches_")
    assert results[0].detected_size == "large"
    assert "meal" in results[0].detected_options


def test_search_detects_feminine_size_form():
    results = search_menu("بيتزا كبيرة")
    assert results[0].item_id.startswith("pizza_flatbread_")
    assert results[0].detected_size == "large"


def test_search_detects_arabic_meal_keyword():
    results = search_menu("برجر وجبة")
    assert results[0].item_id.startswith("sandwiches_")
    assert "meal" in results[0].detected_options


def test_item_price_size_vs_same_named_option_in_other_group():
    assert item_price("pizza_flatbread_01", size="medium", option_ids=[]) == 4200
    assert item_price("pizza_flatbread_01", size="medium", option_ids=["medium"]) == 4200


def test_item_price_duplicate_option_ids_not_double_counted():
    price = item_price("breakfast_01", size=None, option_ids=["cheese", "cheese"])
    assert price == 2600


def test_starting_price_is_base_plus_required_minimums():
    item = get_item("pizza_flatbread_01")
    assert _starting_price_halalas(item) == 3200


def test_search_ambiguous_true_on_near_tie():
    results = search_menu("ابغى برجر large meal")
    assert results[0].ambiguous is True


def test_search_ambiguous_false_on_clear_match():
    results = search_menu("بيتزا مارغريتا")
    assert results[0].ambiguous is False


def test_search_ambiguous_false_on_no_results():
    assert search_menu("qwertyzzz nonsense") == []


def test_list_category_returns_items_in_category():
    items = list_category("appetizers")
    assert len(items) == 12
    assert all(item.category_id == "appetizers" for item in items)
    assert any(item.item_id == "appetizers_01" for item in items)


def test_list_category_unknown_returns_empty():
    assert list_category("not_a_real_category") == []
