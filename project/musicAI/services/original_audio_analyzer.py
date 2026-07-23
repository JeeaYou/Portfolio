"""Original audio feature analysis for MusicAI."""

import librosa
import numpy as np
import parselmouth
from parselmouth.praat import call

from ..constants.analysis_constants import (
    MAJOR_PROFILE,
    MINOR_PROFILE,
    NOTE_NAMES,
)
from ..utils.audio_utils import to_float_list


# =============================
# Language settings
# =============================

SUPPORTED_LANGUAGES = {"ko", "en", "zh"}


def normalize_lang(lang):
    """Returns a supported language code or Korean as the default."""
    return lang if lang in SUPPORTED_LANGUAGES else "ko"


# =============================
# Tempo descriptions
# =============================

# Each entry contains:
# maximum BPM, musical term, translated category, and translated description.
TEMPO_INFO = [
    (
        24,
        "Larghissimo",
        {"ko": "극도로 느림", "en": "Very Very Slow", "zh": "极其缓慢"},
        {
            "ko": "거의 움직임이 느껴지지 않을 정도로 매우 느리게",
            "en": "Extremely slow, with almost no sense of movement",
            "zh": "极其缓慢，几乎感觉不到移动",
        },
    ),
    (
        60,
        "Largo",
        {"ko": "매우 느림", "en": "Very Slow", "zh": "非常缓慢"},
        {
            "ko": "아주 느리고 폭넓게",
            "en": "Very slow and broad",
            "zh": "非常缓慢而宽广",
        },
    ),
    (
        76,
        "Adagio",
        {"ko": "느림", "en": "Slow", "zh": "缓慢"},
        {
            "ko": "천천히, 편안하게",
            "en": "Slowly and comfortably",
            "zh": "缓慢而舒适地",
        },
    ),
    (
        108,
        "Andante",
        {"ko": "약간 느림", "en": "Moderately Slow", "zh": "中等偏慢"},
        {
            "ko": "걷는 속도로",
            "en": "At a walking pace",
            "zh": "以步行的速度",
        },
    ),
    (
        120,
        "Moderato",
        {"ko": "보통", "en": "Medium", "zh": "中等"},
        {
            "ko": "보통 빠르기",
            "en": "At a moderate speed",
            "zh": "以中等速度",
        },
    ),
    (
        156,
        "Allegro",
        {"ko": "빠름", "en": "Fast", "zh": "快速"},
        {
            "ko": "빠르고 경쾌하게",
            "en": "Fast and lively",
            "zh": "快速而欢快地",
        },
    ),
    (
        168,
        "Vivace",
        {"ko": "매우 빠름", "en": "Very Fast", "zh": "非常快速"},
        {
            "ko": "생기 있고 아주 빠르게",
            "en": "Very fast and lively",
            "zh": "活泼而快速地",
        },
    ),
    (
        200,
        "Presto",
        {"ko": "매우 빠름", "en": "Very Fast", "zh": "非常快速"},
        {
            "ko": "매우 빠르게",
            "en": "Very fast",
            "zh": "非常快速地",
        },
    ),
    (
        float("inf"),
        "Prestissimo",
        {"ko": "극도로 빠름", "en": "Extremely Fast", "zh": "极其快速"},
        {
            "ko": "가능한 한 아주 빠르게",
            "en": "As fast as possible",
            "zh": "尽可能快地",
        },
    ),
]


# =============================
# Analysis result translations
# =============================

GENRE_TEXT = {
    "ballad": {
        "ko": "발라드 / 어쿠스틱 계열",
        "en": "Ballad / Acoustic-like",
        "zh": "抒情 / 原声风格",
    },
    "pop": {
        "ko": "팝 계열",
        "en": "Pop-like",
        "zh": "流行风格",
    },
    "dance": {
        "ko": "댄스 / EDM 계열",
        "en": "Dance / EDM-like",
        "zh": "舞曲 / EDM风格",
    },
    "rock": {
        "ko": "록 / 일렉트로닉 계열",
        "en": "Rock / Electronic-like",
        "zh": "摇滚 / 电子风格",
    },
    "jazz": {
        "ko": "재즈 / 어쿠스틱 계열",
        "en": "Jazz / Acoustic-like",
        "zh": "爵士 / 原声风格",
    },
    "mixed": {
        "ko": "혼합 / 알 수 없음",
        "en": "Mixed / Unknown",
        "zh": "混合 / 未知",
    },
}

RHYTHM_TEXT = {
    "not_detected": {
        "ko": "리듬이 명확하게 감지되지 않음",
        "en": "Rhythm not clearly detected",
        "zh": "未能清晰检测到节奏",
    },
    "strong_steady": {
        "ko": "강하고 일정한 비트",
        "en": "Strong and steady beat",
        "zh": "强烈而稳定的节拍",
    },
    "steady": {
        "ko": "일정한 리듬",
        "en": "Steady rhythm",
        "zh": "稳定的节奏",
    },
    "moderate_variation": {
        "ko": "적당한 리듬 변화",
        "en": "Moderate rhythmic variation",
        "zh": "适度的节奏变化",
    },
    "irregular_expressive": {
        "ko": "불규칙하거나 표현적인 리듬",
        "en": "Irregular or expressive rhythm",
        "zh": "不规则或富有表现力的节奏",
    },
}

MOOD_TEXT = {
    "melancholic": {
        "ko": "우울 / 감성",
        "en": "Melancholic / Emotional",
        "zh": "忧郁 / 感性",
    },
    "bright": {
        "ko": "밝음 / 활기참",
        "en": "Bright / Energetic",
        "zh": "明亮 / 充满活力",
    },
    "powerful": {
        "ko": "강렬 / 강함",
        "en": "Powerful / Intense",
        "zh": "强劲 / 强烈",
    },
    "calm": {
        "ko": "차분 / 부드러움",
        "en": "Calm / Soft",
        "zh": "平静 / 柔和",
    },
    "dramatic": {
        "ko": "극적 / 감성",
        "en": "Dramatic / Emotional",
        "zh": "戏剧性 / 感性",
    },
    "groovy": {
        "ko": "그루비 / 기분 상승",
        "en": "Groovy / Uplifting",
        "zh": "富有律动感 / 振奋",
    },
    "neutral": {
        "ko": "중립 / 균형",
        "en": "Neutral / Balanced",
        "zh": "中性 / 平衡",
    },
}

BEAT_STRENGTH_TEXT = {
    "weak": {"ko": "약함", "en": "Weak", "zh": "弱"},
    "moderate": {"ko": "보통", "en": "Moderate", "zh": "中等"},
    "strong": {"ko": "강함", "en": "Strong", "zh": "强"},
    "very_strong": {"ko": "매우 강함", "en": "Very Strong", "zh": "非常强"},
}

BEAT_REGULARITY_TEXT = {
    "very_steady": {"ko": "매우 일정함", "en": "Very steady", "zh": "非常稳定"},
    "steady": {"ko": "일정함", "en": "Steady", "zh": "稳定"},
    "moderate": {"ko": "보통", "en": "Moderately varied", "zh": "有一定变化"},
    "irregular": {"ko": "불규칙함", "en": "Irregular", "zh": "不规则"},
}

DYNAMIC_RANGE_TEXT = {
    "very_low": {"ko": "매우 적음", "en": "Very little", "zh": "非常小"},
    "low": {"ko": "적음", "en": "Little", "zh": "较小"},
    "moderate": {"ko": "적당함", "en": "Moderate", "zh": "适中"},
    "high": {"ko": "큼", "en": "Wide", "zh": "较大"},
}

HNR_TEXT = {
    "unavailable": {
        "ko": "보컬 선명도를 측정할 수 없음",
        "en": "Harmonic clarity could not be measured",
        "zh": "无法测量声音清晰度",
    },
    "noise_dominant": {
        "ko": "잡음 성분이 많음",
        "en": "Noise components are dominant",
        "zh": "噪声成分较多",
    },
    "low": {
        "ko": "보컬 선명도가 낮음",
        "en": "Low harmonic clarity",
        "zh": "声音清晰度较低",
    },
    "moderate": {
        "ko": "보컬과 잡음이 혼합됨",
        "en": "Vocal and noisy components are mixed",
        "zh": "声音与噪声成分混合",
    },
    "clear": {
        "ko": "보컬이 비교적 선명함",
        "en": "Relatively clear vocal",
        "zh": "声音较清晰",
    },
    "very_clear": {
        "ko": "보컬이 매우 선명함",
        "en": "Very clear vocal",
        "zh": "声音非常清晰",
    },
}

DANCEABILITY_TEXT = {
    "low": {"ko": "낮음", "en": "Low", "zh": "较低"},
    "slightly_low": {"ko": "다소 낮음", "en": "Slightly low", "zh": "偏低"},
    "moderate": {"ko": "보통", "en": "Moderate", "zh": "中等"},
    "high": {"ko": "적합함", "en": "Dance-friendly", "zh": "适合"},
    "very_high": {
        "ko": "매우 적합함",
        "en": "Very dance-friendly",
        "zh": "非常适合",
    },
}

SPECTRAL_CENTROID_TEXT = {
    "dark": {
        "ko": "어둡고 부드러운 음색",
        "en": "Dark and soft tone",
        "zh": "低沉柔和的音色",
    },
    "warm": {
        "ko": "부드럽고 따뜻한 음색",
        "en": "Soft and warm tone",
        "zh": "柔和温暖的音色",
    },
    "bright": {
        "ko": "밝고 선명한 음색",
        "en": "Bright and clear tone",
        "zh": "明亮清晰的音色",
    },
    "very_bright": {
        "ko": "매우 밝고 날카로운 음색",
        "en": "Very bright and sharp tone",
        "zh": "非常明亮尖锐的音色",
    },
}

SPECTRAL_FLATNESS_TEXT = {
    "very_low": {
        "ko": "노이즈 성분이 매우 적음",
        "en": "Very low noise content",
        "zh": "噪声成分非常少",
    },
    "low": {
        "ko": "노이즈 성분이 적음",
        "en": "Low noise content",
        "zh": "噪声成分较少",
    },
    "high": {
        "ko": "노이즈 성분이 많음",
        "en": "High noise content",
        "zh": "噪声成分较多",
    },
    "very_high": {
        "ko": "노이즈 성분이 매우 많음",
        "en": "Very high noise content",
        "zh": "噪声成分非常多",
    },
}

SPECTRAL_FLUX_TEXT = {
    "very_low": {"ko": "매우 적음", "en": "Very little", "zh": "非常少"},
    "low": {"ko": "적음", "en": "Little tonal change", "zh": "较少"},
    "high": {"ko": "많음", "en": "Frequent", "zh": "较多"},
    "very_high": {"ko": "매우 많음", "en": "Very frequent", "zh": "非常多"},
}

ZERO_CROSSING_TEXT = {
    "very_low": {"ko": "매우 낮음", "en": "Very low", "zh": "非常低"},
    "low": {"ko": "낮음", "en": "Low", "zh": "较低"},
    "high": {"ko": "높음", "en": "High", "zh": "较高"},
    "very_high": {"ko": "매우 높음", "en": "Very high", "zh": "非常高"},
}


# =============================
# Original audio analysis
# =============================

def analyze_original_audio_librosa(audio_file, sample_rate=44100, lang="ko"):
    """Analyses musical, rhythmic, energy, and spectral audio features."""
    lang = normalize_lang(lang)
    y, sr = librosa.load(audio_file, sr=sample_rate, mono=True)

    # Calculate the total audio duration.
    duration = librosa.get_duration(y=y, sr=sr)
    duration_text = f"{int(duration // 60)}:{int(duration % 60):02d}"

    # Remove leading and trailing silence.
    y_trimmed, _ = librosa.effects.trim(y, top_db=35)

    if len(y_trimmed) == 0:
        y_trimmed = y

    # -----------------------------
    # Key and chroma
    # -----------------------------

    chroma_mean = analyze_chroma_profile(y_trimmed, sr)
    best_score, best_key, best_scale, scale_text = -1, None, None, None

    # Compare the chroma values with each major and minor key profile.
    for index in range(12):
        major_profile = np.roll(MAJOR_PROFILE, index)
        minor_profile = np.roll(MINOR_PROFILE, index)

        major_profile /= np.linalg.norm(major_profile)
        minor_profile /= np.linalg.norm(minor_profile)

        major_score = np.dot(chroma_mean["value"], major_profile)
        minor_score = np.dot(chroma_mean["value"], minor_profile)

        if major_score > best_score:
            best_score = major_score
            best_key = NOTE_NAMES[index]
            best_scale = "major"
            scale_text = "大调" if lang == "zh" else "Major"

        if minor_score > best_score:
            best_score = minor_score
            best_key = NOTE_NAMES[index]
            best_scale = "minor"
            scale_text = "小调" if lang == "zh" else "Minor"

    # music_key is used internally, while music_key_text is displayed to the user.
    music_key = f"{best_key} {best_scale}"
    music_key_text = f"{best_key} {scale_text}"

    # -----------------------------
    # Tempo and beat
    # -----------------------------

    tempo, beats = librosa.beat.beat_track(y=y_trimmed, sr=sr)
    tempo = round(float(np.asarray(tempo).flatten()[0]))

    onset_env = librosa.onset.onset_strength(y=y_trimmed, sr=sr)
    beat_strength = analyze_beat_strength(float(np.mean(onset_env)), lang)
    beat_regularity = analyze_beat_regularity(beats, lang)
    rhythm_pattern = analyze_rhythm_pattern(beats, onset_env, sr, lang)

    # -----------------------------
    # Energy and RMS
    # -----------------------------

    rms = librosa.feature.rms(y=y_trimmed)[0]
    avg_rms = float(np.mean(rms))

    rms_db = 20 * np.log10(avg_rms + 1e-10)
    energy_score = max(0, min(100, (rms_db + 60) / 60 * 100))

    if energy_score < 35:
        energy_level_key = "low"
    elif energy_score < 70:
        energy_level_key = "medium"
    else:
        energy_level_key = "high"

    energy_level_text = {
        "low": {"ko": "낮음", "en": "Low", "zh": "低"},
        "medium": {"ko": "중간", "en": "Medium", "zh": "中"},
        "high": {"ko": "높음", "en": "High", "zh": "高"},
    }

    energy_level = energy_level_text[energy_level_key][lang]

    # -----------------------------
    # Spectral features
    # -----------------------------

    spectral_centroid = analyze_spectral_centroid(y_trimmed, sr, lang)

    spectral_bandwidth = librosa.feature.spectral_bandwidth(
        y=y_trimmed,
        sr=sr,
    )[0]
    avg_spectral_bandwidth = float(np.mean(spectral_bandwidth))

    spectral_rolloff = librosa.feature.spectral_rolloff(
        y=y_trimmed,
        sr=sr,
    )[0]
    avg_spectral_rolloff = float(np.mean(spectral_rolloff))

    spectral_flatness = analyze_spectral_flatness(y_trimmed, lang)
    zero_crossing = analyze_zero_crossing_rate(y_trimmed, lang)

    # Normalise the STFT before calculating spectral flux.
    stft = np.abs(librosa.stft(y_trimmed))
    stft_norm = stft / (np.sum(stft, axis=0, keepdims=True) + 1e-8)
    spectral_flux = analyze_spectral_flux(stft_norm, lang)

    spectral_contrast = librosa.feature.spectral_contrast(
        y=y_trimmed,
        sr=sr,
    )
    spectral_contrast_mean = np.mean(spectral_contrast, axis=1)

    # -----------------------------
    # MFCC and tonal centroid
    # -----------------------------

    mfcc = librosa.feature.mfcc(y=y_trimmed, sr=sr, n_mfcc=20)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)

    try:
        harmonic_y = librosa.effects.harmonic(y_trimmed)
        tonnetz_mean = np.mean(
            librosa.feature.tonnetz(y=harmonic_y, sr=sr),
            axis=1,
        )
    except Exception:
        tonnetz_mean = np.zeros(6)

    # -----------------------------
    # Dynamic range and HNR
    # -----------------------------

    rms_db_frames = librosa.amplitude_to_db(rms, ref=np.max)

    dynamic_range = analyze_dynamic_range(
        np.percentile(rms_db_frames, 95)
        - np.percentile(rms_db_frames, 10),
        lang,
    )

    hnr = analyze_hnr(audio_file, lang)

    # -----------------------------
    # Danceability, mood, and genre
    # -----------------------------

    tempo_score = 1.0 - min(abs(tempo - 120) / 120, 1.0)

    danceability = analyze_danceability(
        tempo_score,
        beat_strength["value"],
        beat_regularity["value"],
        lang,
    )

    mood = analyze_mood(
        music_key,
        tempo,
        energy_score,
        spectral_centroid["value"],
        danceability["value"],
        lang,
    )

    genre = analyze_genre(
        tempo,
        energy_score,
        spectral_centroid["value"],
        zero_crossing["value"],
        spectral_flatness["value"],
        danceability["value"],
        lang,
    )

    return {
        "duration": round(duration, 2),
        "duration_text": duration_text,
        "key": music_key_text,
        "key_confidence": round(float(best_score), 3),
        "key_method": "librosa",
        "tempo": tempo,
        "rhythm_pattern": rhythm_pattern,
        "beat_count": int(len(beats)),
        "beat_strength": beat_strength["text"],
        "beat_regularity": beat_regularity["text"],
        "energy_score": int(energy_score),
        "energy_level": energy_level,
        "rms": round(avg_rms, 5),
        "genre": genre,
        "mood": mood,
        "spectral_centroid": spectral_centroid["text"],
        "spectral_centroid_value": spectral_centroid["value"],
        "spectral_bandwidth": round(avg_spectral_bandwidth, 2),
        "spectral_rolloff": round(avg_spectral_rolloff, 2),
        "spectral_flatness": spectral_flatness["text"],
        "spectral_flux": spectral_flux["text"],
        "zero_crossing_rate": zero_crossing["text"],
        "mfcc_mean": to_float_list(mfcc_mean),
        "mfcc_std": to_float_list(mfcc_std),
        "spectral_contrast_mean": to_float_list(spectral_contrast_mean),
        "chroma_mean": chroma_mean["text"],
        "tonnetz_mean": to_float_list(tonnetz_mean),
        "dynamic_range": dynamic_range["text"],
        "dynamic_range_value": round(float(dynamic_range["value"]), 2),
        "hnr": hnr["text"],
        "hnr_value": hnr["value_db"],
        "danceability": danceability["text"],
        "danceability_value": danceability["value"],
    }


# =============================
# Tempo, genre, mood, and rhythm
# =============================

def get_tempo_info(bpm, lang="ko"):
    """Returns the musical tempo term and its translated description."""
    lang = normalize_lang(lang)

    for max_bpm, tempo_name, categories, descriptions in TEMPO_INFO:
        if bpm <= max_bpm:
            return {
                "tempo_name": tempo_name,
                "tempo_category": categories[lang],
                "description": descriptions[lang],
            }

    raise RuntimeError("Tempo information could not be determined.")


def analyze_genre(
    bpm,
    energy_score,
    spectral_centroid=None,
    zero_crossing_rate=None,
    spectral_flatness=None,
    danceability=None,
    lang="ko",
):
    """Estimates a broad genre category from the analysed audio features."""
    lang = normalize_lang(lang)

    scores = {
        "ballad": 0,
        "pop": 0,
        "dance": 0,
        "rock": 0,
        "jazz": 0,
        "mixed": 0,
    }

    if bpm >= 120:
        scores["dance"] += 2
    if energy_score >= 70:
        scores["dance"] += 2
    if danceability is not None and danceability >= 55:
        scores["dance"] += 1
    if spectral_flatness is not None and spectral_flatness >= 0.03:
        scores["dance"] += 1

    if 90 <= bpm <= 130:
        scores["pop"] += 2
    if 45 <= energy_score <= 75:
        scores["pop"] += 2
    if danceability is not None and 35 <= danceability <= 65:
        scores["pop"] += 1

    if bpm < 95:
        scores["ballad"] += 2
    if energy_score < 60:
        scores["ballad"] += 2
    if spectral_centroid is not None and spectral_centroid < 2200:
        scores["ballad"] += 1
    if zero_crossing_rate is not None and zero_crossing_rate < 0.05:
        scores["ballad"] += 1

    if bpm >= 130:
        scores["rock"] += 1
    if energy_score >= 65:
        scores["rock"] += 1
    if spectral_centroid is not None and spectral_centroid >= 2500:
        scores["rock"] += 1
    if zero_crossing_rate is not None and zero_crossing_rate >= 0.08:
        scores["rock"] += 1

    if spectral_centroid is not None and spectral_centroid < 1800:
        scores["jazz"] += 1
    if energy_score < 65:
        scores["jazz"] += 1

    best_genre = max(scores, key=scores.get)

    if scores[best_genre] == 0:
        best_genre = "mixed"

    return GENRE_TEXT[best_genre][lang]


def analyze_rhythm_pattern(beats, onset_env, sr, lang="ko"):
    """Classifies the rhythm using beat timing variation and onset strength."""
    lang = normalize_lang(lang)

    if beats is None or len(beats) < 3:
        return RHYTHM_TEXT["not_detected"][lang]

    beat_intervals = np.diff(librosa.frames_to_time(beats, sr=sr))

    if len(beat_intervals) == 0:
        return RHYTHM_TEXT["not_detected"][lang]

    interval_mean = float(np.mean(beat_intervals))
    interval_std = float(np.std(beat_intervals))
    beat_variation = interval_std / (interval_mean + 1e-8)
    beat_strength = float(np.mean(onset_env))

    if beat_variation < 0.08 and beat_strength >= 1.5:
        key = "strong_steady"
    elif beat_variation < 0.12:
        key = "steady"
    elif beat_variation < 0.2:
        key = "moderate_variation"
    else:
        key = "irregular_expressive"

    return RHYTHM_TEXT[key][lang]


def analyze_mood(
    music_key,
    tempo,
    energy_score,
    spectral_centroid,
    danceability,
    lang="ko",
):
    """Estimates the musical mood from the key and audio features."""
    lang = normalize_lang(lang)

    key_lower = music_key.lower() if music_key else ""
    is_minor = "minor" in key_lower
    is_major = "major" in key_lower

    if is_minor and energy_score < 55 and tempo <= 115:
        mood_key = "melancholic"
    elif is_major and energy_score >= 65 and tempo >= 110:
        mood_key = "bright"
    elif energy_score >= 75 and spectral_centroid >= 2500:
        mood_key = "powerful"
    elif energy_score < 45 and tempo < 90:
        mood_key = "calm"
    elif is_minor and energy_score >= 60:
        mood_key = "dramatic"
    elif danceability >= 60 and energy_score >= 60:
        mood_key = "groovy"
    else:
        mood_key = "neutral"

    return MOOD_TEXT[mood_key][lang]


def analyze_beat_strength(beat_strength, lang="ko"):
    """Classifies the average onset strength."""
    lang = normalize_lang(lang)

    if beat_strength < 0.5:
        key = "weak"
    elif beat_strength < 1.0:
        key = "moderate"
    elif beat_strength < 1.5:
        key = "strong"
    else:
        key = "very_strong"

    return {
        "value": beat_strength,
        "text": BEAT_STRENGTH_TEXT[key][lang],
    }


def analyze_beat_regularity(beats, lang="ko"):
    """Calculates and classifies beat regularity."""
    lang = normalize_lang(lang)

    beat_regularity = (
        1.0 / (np.std(np.diff(beats)) + 1e-6)
        if len(beats) > 2
        else 0
    )

    if beat_regularity >= 0.92:
        key = "very_steady"
    elif beat_regularity >= 0.85:
        key = "steady"
    elif beat_regularity >= 0.70:
        key = "moderate"
    else:
        key = "irregular"

    return {
        "value": beat_regularity,
        "text": BEAT_REGULARITY_TEXT[key][lang],
    }


def analyze_dynamic_range(dynamic_range, lang="ko"):
    """Classifies the difference between loud and quiet audio frames."""
    lang = normalize_lang(lang)

    if dynamic_range < 6:
        key = "very_low"
    elif dynamic_range < 10:
        key = "low"
    elif dynamic_range < 18:
        key = "moderate"
    else:
        key = "high"

    return {
        "text": DYNAMIC_RANGE_TEXT[key][lang],
        "value": dynamic_range,
    }


def analyze_hnr(audio, lang="ko"):
    """Calculates the Harmonic-to-Noise Ratio using Parselmouth."""
    lang = normalize_lang(lang)

    try:
        sound = parselmouth.Sound(str(audio))
        harmonicity = call(sound, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
        hnr = float(call(harmonicity, "Get mean", 0, 0))

        if not np.isfinite(hnr):
            raise ValueError("Invalid HNR result.")

    except Exception:
        return {
            "value_db": None,
            "text": HNR_TEXT["unavailable"][lang],
        }

    if hnr < 0:
        key = "noise_dominant"
    elif hnr < 5:
        key = "low"
    elif hnr < 10:
        key = "moderate"
    elif hnr < 20:
        key = "clear"
    else:
        key = "very_clear"

    return {
        "value_db": round(hnr, 2),
        "text": HNR_TEXT[key][lang],
    }


def analyze_danceability(
    tempo_score,
    beat_strength,
    beat_regularity,
    lang="ko",
):
    """Calculates a danceability score from tempo and beat features."""
    lang = normalize_lang(lang)

    danceability = (
        0.4 * tempo_score
        + 0.3 * min(beat_strength / 5, 1.0)
        + 0.3 * min(beat_regularity / 10, 1.0)
    ) * 100

    if danceability < 30:
        key = "low"
    elif danceability < 50:
        key = "slightly_low"
    elif danceability < 70:
        key = "moderate"
    elif danceability < 85:
        key = "high"
    else:
        key = "very_high"

    return {
        "value": round(danceability),
        "text": DANCEABILITY_TEXT[key][lang],
    }


# =============================
# Spectral analysis
# =============================

def analyze_spectral_centroid(y_trimmed, sr, lang="ko"):
    """Calculates and classifies the perceived brightness of the audio."""
    lang = normalize_lang(lang)

    spectral_centroid = librosa.feature.spectral_centroid(
        y=y_trimmed,
        sr=sr,
    )[0]

    value = float(np.mean(spectral_centroid))

    if value < 1500:
        key = "dark"
    elif value < 2500:
        key = "warm"
    elif value < 4000:
        key = "bright"
    else:
        key = "very_bright"

    return {
        "value": round(value),
        "text": SPECTRAL_CENTROID_TEXT[key][lang],
    }


def analyze_spectral_flatness(y, lang="ko"):
    """Measures and classifies noise-like spectral content."""
    lang = normalize_lang(lang)

    spectral_flatness = librosa.feature.spectral_flatness(y=y)[0]
    value = float(np.mean(spectral_flatness))

    if value < 0.001:
        key = "very_low"
    elif value < 0.01:
        key = "low"
    elif value < 0.05:
        key = "high"
    else:
        key = "very_high"

    return {
        "value": round(value, 6),
        "text": SPECTRAL_FLATNESS_TEXT[key][lang],
    }


def analyze_spectral_flux(stft_norm, lang="ko"):
    """Measures spectral changes between consecutive audio frames."""
    lang = normalize_lang(lang)

    spectral_flux = np.sqrt(
        np.sum(
            np.diff(stft_norm, axis=1) ** 2,
            axis=0,
        )
    )

    value = float(np.mean(spectral_flux))

    if value < 0.02:
        key = "very_low"
    elif value < 0.05:
        key = "low"
    elif value < 0.10:
        key = "high"
    else:
        key = "very_high"

    return {
        "value": round(value, 5),
        "text": SPECTRAL_FLUX_TEXT[key][lang],
    }


def analyze_zero_crossing_rate(y, lang="ko"):
    """Measures and classifies waveform sign changes."""
    lang = normalize_lang(lang)

    zero_crossing = librosa.feature.zero_crossing_rate(y=y)[0]
    value = float(np.mean(zero_crossing))

    if value < 0.02:
        key = "very_low"
    elif value < 0.05:
        key = "low"
    elif value < 0.10:
        key = "high"
    else:
        key = "very_high"

    return {
        "value": round(value, 6),
        "text": ZERO_CROSSING_TEXT[key][lang],
    }


def analyze_chroma_profile(y_trimmed, sr):
    """Calculates the normalised strength of the twelve pitch classes."""
    chroma = librosa.feature.chroma_cqt(y=y_trimmed, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)
    chroma_mean /= np.linalg.norm(chroma_mean) + 1e-8

    if len(chroma_mean) != 12:
        raise ValueError("chroma_mean must contain 12 pitch-class values.")

    max_value = float(np.max(chroma_mean))

    if max_value <= 0:
        return {
            "text": [],
            "value": np.zeros(12),
        }

    ratios = chroma_mean / max_value

    strong_notes = [
        note_name
        for note_name, ratio in zip(NOTE_NAMES, ratios)
        if ratio >= 0.6
    ]

    return {
        "text": strong_notes,
        "value": chroma_mean,
    }