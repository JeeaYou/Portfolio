import librosa
import torch
from transformers import AutoProcessor, AutoModelForAudioClassification


# =============================
# AST model cache
# =============================

_AST_PROCESSOR = None
_AST_MODEL = None


# =============================
# AST model loading
# =============================

def load_ast_model():
    model_name = "MIT/ast-finetuned-audioset-10-10-0.4593"

    print("AST model loading...")

    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModelForAudioClassification.from_pretrained(model_name)
    model.eval()

    print("AST model loaded")

    return processor, model


def get_ast_model():
    global _AST_PROCESSOR, _AST_MODEL

    if _AST_PROCESSOR is None or _AST_MODEL is None:
        _AST_PROCESSOR, _AST_MODEL = load_ast_model()

    return _AST_PROCESSOR, _AST_MODEL


# =============================
# Background instrument analysis
# =============================

def detect_background_instruments_ast(
    background_file,
    processor,
    model,
    threshold=0.008,
    top_n=10,
    lang="ko",
):
    if lang not in ("ko", "en", "zh"):
        lang = "ko"

    audio, _ = librosa.load(
        background_file,
        sr=16000,
        mono=True,
    )

    inputs = processor(
        audio,
        sampling_rate=16000,
        return_tensors="pt",
    )

    with torch.no_grad():
        outputs = model(**inputs)

    scores = torch.sigmoid(outputs.logits[0])
    id2label = model.config.id2label

    instrument_groups = {
        "drums_percussion": [
            "drum",
            "drum kit",
            "snare drum",
            "bass drum",
            "cymbal",
            "percussion",
            "wood block",
            "cowbell",
            "hi-hat",
            "tabla",
            "bongo",
            "conga",
        ],
        "electronic": [
            "synthesizer",
            "drum machine",
            "sampler",
        ],
        "piano_keyboard": [
            "piano",
            "electric piano",
            "keyboard",
        ],
        "guitar": [
            "guitar",
            "electric guitar",
            "acoustic guitar",
        ],
        "bass": [
            "bass guitar",
            "double bass",
            "electric bass",
        ],
        "strings": [
            "violin",
            "viola",
            "cello",
            "string",
            "harp",
        ],
        "brass": [
            "trumpet",
            "trombone",
            "brass",
            "horn",
        ],
        "woodwinds": [
            "flute",
            "clarinet",
            "saxophone",
            "oboe",
        ],
        "organ_accordion": [
            "organ",
            "accordion",
        ],
    }

    instrument_text = {
        "drums_percussion": {
            "ko": "드럼 / 타악기",
            "en": "Drums / Percussion",
            "zh": "鼓 / 打击乐器",
        },
        "electronic": {
            "ko": "전자 악기",
            "en": "Electronic Instruments",
            "zh": "电子乐器",
        },
        "piano_keyboard": {
            "ko": "피아노 / 키보드",
            "en": "Piano / Keyboard",
            "zh": "钢琴 / 键盘",
        },
        "guitar": {
            "ko": "기타",
            "en": "Guitar",
            "zh": "吉他",
        },
        "bass": {
            "ko": "베이스",
            "en": "Bass",
            "zh": "贝斯",
        },
        "strings": {
            "ko": "현악기",
            "en": "Strings",
            "zh": "弦乐器",
        },
        "brass": {
            "ko": "금관악기",
            "en": "Brass",
            "zh": "铜管乐器",
        },
        "woodwinds": {
            "ko": "목관악기",
            "en": "Woodwinds",
            "zh": "木管乐器",
        },
        "organ_accordion": {
            "ko": "오르간 / 아코디언",
            "en": "Organ / Accordion",
            "zh": "风琴 / 手风琴",
        },
    }

    detected_groups = {}

    top_scores, top_indices = torch.topk(
        scores,
        min(30, len(scores)),
    )

    for score, idx in zip(top_scores, top_indices):
        label = id2label[int(idx)]
        score_value = float(score)
        label_lower = label.lower()

        for group_key, keywords in instrument_groups.items():
            if not any(keyword in label_lower for keyword in keywords):
                continue

            if group_key not in detected_groups:
                detected_groups[group_key] = {
                    "instrument": instrument_text[group_key][lang],
                    "instrument_key": group_key,
                    "score": score_value,
                    "percentage": round(score_value * 100, 1),
                    "matched_labels": [label],
                }
                continue

            group = detected_groups[group_key]

            if score_value > group["score"]:
                group["score"] = score_value
                group["percentage"] = round(score_value * 100, 1)

            group["matched_labels"].append(label)

    detected = [
        info
        for info in detected_groups.values()
        if info["score"] >= threshold
    ]

    detected = sorted(
        detected,
        key=lambda item: item["score"],
        reverse=True,
    )[:top_n]

    return {
        "instrument_count": len(detected),
        "instruments": detected,
    }