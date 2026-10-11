from src.speech_text import number_to_words, to_spoken_arabic


def test_number_to_words_basic_range():
    assert number_to_words(0) == "صفر"
    assert number_to_words(1) == "واحد"
    assert number_to_words(9) == "تسعة"
    assert number_to_words(10) == "عشرة"
    assert number_to_words(11) == "احدى عشر"
    assert number_to_words(19) == "تسعة عشر"
    assert number_to_words(20) == "عشرين"
    assert number_to_words(22) == "اثنين وعشرين"
    assert number_to_words(87) == "سبعة وثمانين"
    assert number_to_words(100) == "مية"
    assert number_to_words(101) == "مية وواحد"
    assert number_to_words(999) == "تسعمية وتسعة وتسعين"


def test_number_to_words_out_of_range_raises():
    try:
        number_to_words(1000)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_price_with_halves():
    assert to_spoken_arabic("المجموع 87.50 ريال") == "المجموع سبعة وثمانين ريال ونص"


def test_price_whole_number_with_decimals():
    assert to_spoken_arabic("المجموع 22.00 ريال") == "المجموع اثنين وعشرين ريال"


def test_price_singular_riyal():
    assert to_spoken_arabic("المجموع 1 ريال") == "المجموع ريال واحد"


def test_price_arbitrary_cents():
    assert to_spoken_arabic("السعر 5.25 ريال") == "السعر خمسة ريال وخمسة وعشرين هللة"


def test_quantity_before_dish_western_digit():
    assert to_spoken_arabic("عطيتك 2 شاورما") == "عطيتك اثنين شاورما"


def test_quantity_before_dish_arabic_indic_digit():
    assert to_spoken_arabic("عطيتك ٢ شاورما") == "عطيتك اثنين شاورما"


def test_order_id_read_digit_by_digit_western():
    assert to_spoken_arabic("رقم طلبك 353967") == "رقم طلبك ثلاثة خمسة ثلاثة تسعة ستة سبعة"


def test_order_id_read_digit_by_digit_arabic_indic():
    assert to_spoken_arabic("رقم طلبك ٣٥٣٩٦٧") == "رقم طلبك ثلاثة خمسة ثلاثة تسعة ستة سبعة"


def test_mixed_price_and_order_id_in_one_sentence():
    text = "تم تأكيد الطلب رقم 353967 والمجموع 42.00 ريال"
    expected = "تم تأكيد الطلب رقم ثلاثة خمسة ثلاثة تسعة ستة سبعة والمجموع اثنين وأربعين ريال"
    assert to_spoken_arabic(text) == expected


def test_text_without_numbers_unchanged():
    assert to_spoken_arabic("هلا والله كيف حالك") == "هلا والله كيف حالك"
