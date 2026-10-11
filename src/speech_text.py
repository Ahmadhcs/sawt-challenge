import re

ONES = ["صفر", "واحد", "اثنين", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة"]
TEENS = [
    "عشرة",
    "احدى عشر",
    "اثنا عشر",
    "ثلاثة عشر",
    "أربعة عشر",
    "خمسة عشر",
    "ستة عشر",
    "سبعة عشر",
    "ثمانية عشر",
    "تسعة عشر",
]
TENS = {2: "عشرين", 3: "ثلاثين", 4: "أربعين", 5: "خمسين", 6: "ستين", 7: "سبعين", 8: "ثمانين", 9: "تسعين"}
HUNDREDS = {
    1: "مية",
    2: "مئتين",
    3: "ثلاثمية",
    4: "أربعمية",
    5: "خمسمية",
    6: "ستمية",
    7: "سبعمية",
    8: "ثمانمية",
    9: "تسعمية",
}

_ARABIC_INDIC_DIGITS = str.maketrans({chr(0x0660 + i): str(i) for i in range(10)})

_PRICE_PATTERN = re.compile(r"(\d+)\.(\d{2})\s*ريال")
_INTEGER_RIYAL_PATTERN = re.compile(r"(\d+)\s*ريال")
_ORDER_ID_PATTERN = re.compile(r"(?<!\d)\d{6}(?!\d)")
_STANDALONE_NUMBER_PATTERN = re.compile(r"(?<!\d)\d{1,3}(?!\d)")


def number_to_words(n: int) -> str:
    if n == 0:
        return ONES[0]
    if not 0 <= n <= 999:
        raise ValueError(f"number_to_words only covers 0-999, got {n}")

    hundreds_digit, remainder = divmod(n, 100)
    parts = []
    if hundreds_digit:
        parts.append(HUNDREDS[hundreds_digit])

    if remainder:
        if remainder < 10:
            parts.append(ONES[remainder])
        elif remainder < 20:
            parts.append(TEENS[remainder - 10])
        else:
            tens_digit, ones_digit = divmod(remainder, 10)
            parts.append(f"{ONES[ones_digit]} و{TENS[tens_digit]}" if ones_digit else TENS[tens_digit])

    return " و".join(parts)


def _price_to_words(whole: int, cents: int) -> str:
    words = f"ريال {ONES[1]}" if whole == 1 else f"{number_to_words(whole)} ريال"

    if cents == 50:
        words += " ونص"
    elif cents != 0:
        words += f" و{number_to_words(cents)} هللة"

    return words


def to_spoken_arabic(text: str) -> str:
    text = text.translate(_ARABIC_INDIC_DIGITS)

    text = _PRICE_PATTERN.sub(lambda m: _price_to_words(int(m.group(1)), int(m.group(2))), text)
    text = _INTEGER_RIYAL_PATTERN.sub(lambda m: _price_to_words(int(m.group(1)), 0), text)
    text = _ORDER_ID_PATTERN.sub(lambda m: " ".join(number_to_words(int(d)) for d in m.group(0)), text)
    text = _STANDALONE_NUMBER_PATTERN.sub(lambda m: number_to_words(int(m.group(0))), text)

    return text
