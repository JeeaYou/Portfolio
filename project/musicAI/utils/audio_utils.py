import numpy as np


# =============================
# Time formatting
# =============================

DURATION_UNITS = {
    "ko": ("분", "초"),
    "en": ("min", "sec"),
    "zh": ("分", "秒"),
}


def format_duration_text(total_seconds, lang="ko"):
    minutes, seconds = divmod(int(total_seconds), 60)
    minute_unit, second_unit = DURATION_UNITS.get(lang, DURATION_UNITS["ko"])

    if minutes:
        return f"{minutes} {minute_unit} {seconds} {second_unit}"

    return f"{seconds} {second_unit}"


def format_seconds(total_seconds):
    return format_duration_text(total_seconds, lang="en")


# =============================
# NumPy conversion
# =============================

def to_float_list(values, ndigits=5):
    return [
        round(float(value), ndigits)
        for value in np.asarray(values).flatten()
    ]