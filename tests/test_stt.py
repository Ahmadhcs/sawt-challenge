from src.stt import TranscriptionResult, Word, mark_low_confidence


def test_mark_low_confidence_marks_only_words_below_threshold():
    result = TranscriptionResult(
        text="توصيل العليا",
        words=[Word(text="توصيل", confidence=0.95), Word(text="العليا", confidence=0.4)],
    )
    assert mark_low_confidence(result) == "توصيل [غير متأكد: العليا]"


def test_mark_low_confidence_no_marking_when_all_confident():
    result = TranscriptionResult(
        text="توصيل العليا",
        words=[Word(text="توصيل", confidence=0.95), Word(text="العليا", confidence=0.9)],
    )
    assert mark_low_confidence(result) == "توصيل العليا"


def test_mark_low_confidence_empty_words_returns_plain_text():
    result = TranscriptionResult(text="", words=[])
    assert mark_low_confidence(result) == ""


def test_mark_low_confidence_boundary_at_threshold_not_marked():
    # confidence exactly at the 0.6 threshold should not be marked (< 0.6, not <=)
    result = TranscriptionResult(text="كبير", words=[Word(text="كبير", confidence=0.6)])
    assert mark_low_confidence(result) == "كبير"
