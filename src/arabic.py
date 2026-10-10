import re


_TASHKEEL_TATWEEL = re.compile("[\u0640\u064B-\u065F\u0670]")

_CHAR_MAP = {
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ٱ": "ا",
    "ة": "ه",
    "ى": "ي",
}
_CHAR_MAP.update({chr(0x0660 + i): str(i) for i in range(10)})
_CHAR_MAP.update({chr(0x06F0 + i): str(i) for i in range(10)})
_TRANSLATE_TABLE = str.maketrans(_CHAR_MAP)


def normalize_ar(text: str) -> str:
    text = _TASHKEEL_TATWEEL.sub("", text)
    text = text.translate(_TRANSLATE_TABLE)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text



NAME_SYNONYMS: dict[str, str] = {
    "chicken": "دجاج",
    "beef": "لحم",
    "meat": "لحم",
    "cheese": "جبن",
    "مويه": "مياه",
    "بطاطا": "بطاطس",
}


SIZE_KEYWORDS: dict[str, str] = {
    "large": "large",
    "كبير": "large",
    "medium": "medium",
    "وسط": "medium",
    "small": "small",
    "صغير": "small",
}


OPTION_KEYWORDS: dict[str, str] = {
    "meal": "meal",
    "combo": "meal",
    "وجبة": "meal",
    "spicy": "spicy",
    "حار": "spicy",
    "mild": "mild",
    "خفيف": "mild",
    "extra": "extra",
    "اضافي": "extra",
    "without": "without",
    "no": "without",
    "بدون": "without",
}


def extract_keywords(normalized_query: str) -> tuple[str, str | None, list[str]]:
    """Pull size/option words out of a normalized query.

    Returns (remaining_text_for_matching, detected_size, detected_options).
    """
    tokens = normalized_query.split(" ") if normalized_query else []
    remaining = []
    detected_size = None
    detected_options: list[str] = []

    for token in tokens:
        if token in SIZE_KEYWORDS:
            if detected_size is None:
                detected_size = SIZE_KEYWORDS[token]
            continue
        if token in OPTION_KEYWORDS:
            detected_options.append(OPTION_KEYWORDS[token])
            continue
        remaining.append(NAME_SYNONYMS.get(token, token))

    return " ".join(remaining), detected_size, detected_options
