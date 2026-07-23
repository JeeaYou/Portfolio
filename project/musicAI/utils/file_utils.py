import json
from pathlib import Path
import re
from pathlib import Path


def format_display_file_name(file_path):
    file_name = Path(file_path).name
    suffix = Path(file_name).suffix
    stem = Path(file_name).stem

    stem = re.sub(r"^\d+[\s._-]+", "", stem)
    stem = re.sub(r"_+", " ", stem).strip()

    return f"{stem}{suffix}"

# =============================
# JSON file handling
# =============================

def save_json_result(data, file_path):
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)