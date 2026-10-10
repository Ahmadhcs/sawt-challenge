from src.locations import find_branch, find_zone


def test_find_zone_alias_without_al():
    zone = find_zone("عليا")
    assert zone is not None
    assert zone.zone_id == "olaya"


def test_find_zone_english_alias():
    zone = find_zone("Olaya")
    assert zone is not None
    assert zone.zone_id == "olaya"


def test_find_zone_spelling_variant_in_sentence():
    zone = find_zone("انا ساكن في حي النرجس")
    assert zone is not None
    assert zone.zone_id == "narjis"


def test_find_zone_jeddah_neighborhood_maps_to_jed_rawdah():
    zone = find_zone("الزهراء")
    assert zone is not None
    assert zone.branch_id == "jed_rawdah"


def test_find_zone_khobar_returns_none():
    assert find_zone("الخبر") is None


def test_find_branch_by_neighborhood():
    branch = find_branch("الملقا")
    assert branch is not None
    assert branch.branch_id == "ruh_malqa"


def test_find_branch_by_branch_name():
    branch = find_branch("فرع العليا")
    assert branch is not None
    assert branch.branch_id == "ruh_olaya"


def test_find_branch_khobar_returns_none():
    assert find_branch("الخبر") is None
