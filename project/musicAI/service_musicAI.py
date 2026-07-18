import numpy as np
import certifi
import subprocess
import sys
import os
import signal
from pathlib import Path

import librosa
import parselmouth
from parselmouth.praat import call

import torch
import torchcrepe
from transformers import AutoProcessor, AutoModelForAudioClassification

import time
import json
import re
import threading
from flask import request

from .music_db_service import (
    save_music_analysis_to_db,
    mark_analysis_job_success,
    mark_analysis_job_failed,
)

def get_lang():
    lang = request.args.get("lang", "ko")

    return lang

# =============================
# 기본 설정
# =============================

BASE_DIR = Path(__file__).resolve().parent

PROGRESS_DIR = BASE_DIR / "progress"
PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

SEPARATED_DIR = BASE_DIR / "separated"
ANALYSIS_RESULTS_DIR = BASE_DIR / "analysis_results"
ANALYSIS_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# =============================
# 분석 취소 상태 관리
# =============================

_CURRENT_DEMUCS_PROCESSES = {}
_CURRENT_DEMUCS_PROCESSES_LOCK = threading.Lock()

UPDATE_STEP_TEXT = {
    "ko": {
        "original_analyzing": "음악 오디오 원곡 분석 중",
        "original_completed": "음악 오디오 원곡 분석 완료",
        "separating": "음악 오디오 보컬/배경음악 분리 중",
        "separating_percent": "음악 오디오 보컬/배경음악 분리 중",
        "separation_completed": "음악 오디오 보컬/배경음악 분리 완료",
        "pitch_analyzing": "음악 오디오 보컬 피치 분석 중",
        "pitch_completed": "음악 오디오 보컬 피치 분석 완료",
        "instrument_analyzing": "음악 오디오 배경 악기 분석 중",
        "saving": "음악 오디오 결과 저장 중",
        "analysis_completed": "음악 오디오 분석 완료",
    },
    "en": {
        "original_analyzing": "Analyzing the original audio",
        "original_completed": "Original audio analysis completed",
        "separating": "Separating vocals and background music",
        "separating_percent": "Separating vocals and background music",
        "separation_completed": "Vocal and background music separation completed",
        "pitch_analyzing": "Analyzing vocal pitch",
        "pitch_completed": "Vocal pitch analysis completed",
        "instrument_analyzing": "Analyzing background instruments",
        "saving": "Saving audio analysis results",
        "analysis_completed": "Audio analysis completed",
    },
    "zh": {
        "original_analyzing": "正在分析原始音频",
        "original_completed": "原始音频分析完成",
        "separating": "正在分离人声和背景音乐",
        "separating_percent": "正在分离人声和背景音乐",
        "separation_completed": "人声和背景音乐分离完成",
        "pitch_analyzing": "正在分析人声音高",
        "pitch_completed": "人声音高分析完成",
        "instrument_analyzing": "正在分析背景乐器",
        "saving": "正在保存音频分析结果",
        "analysis_completed": "音频分析完成",
    },
}

class AnalysisCancelled(Exception):pass

def format_duration_text(total_seconds, lang="ko"):
    minutes, seconds = int(total_seconds // 60), int(total_seconds % 60)
    units = {"ko": ("분", "초"), "en": ("min", "sec"), "zh": ("分", "秒")}
    minute_unit, second_unit = units.get(lang, units["ko"])
    return f"{minutes} {minute_unit} {seconds} {second_unit}" if minutes > 0 else f"{seconds} {second_unit}"

def terminate_process_tree(process, timeout=3):
    """
    Demucs가 내부적으로 하위 프로세스를 만들 수 있으므로
    부모 process만 terminate하지 않고 프로세스 그룹까지 종료한다.
    macOS/Linux에서는 start_new_session=True로 실행한 뒤 os.killpg를 사용한다.
    """
    if not process or process.poll() is not None:
        return

    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.kill()

            process.wait(timeout=timeout)

    except ProcessLookupError:
        pass
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


NOTE_NAMES = [
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B"
]

MAJOR_PROFILE = np.array([
    6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
    2.52, 5.19, 2.39, 3.66, 2.29, 2.88
])

MINOR_PROFILE = np.array([
    6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
    2.54, 4.75, 3.98, 2.69, 3.34, 3.17
])

# =============================
# 공통 유틸
# =============================

def format_seconds(seconds):
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes} min {secs} sec"


def save_json_result(data, file_path):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def to_float_list(values, ndigits=5):
    return [
        round(float(v), ndigits)
        for v in np.asarray(values).flatten()
    ]


# =============================
# Progress 저장 / 조회 함수
# =============================

def get_progress_path(job_id):
    return PROGRESS_DIR / f"{job_id}.json"


def write_progress(job_id, data):
    if not job_id:
        return

    # progress 폴더가 없으면 매번 자동 생성
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

    progress_path = get_progress_path(job_id)
    temp_path = progress_path.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    temp_path.replace(progress_path)


def read_progress(job_id):
    progress_path = get_progress_path(job_id)

    if not progress_path.exists():
        return None

    try:
        with open(progress_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def make_progress_files(
        audio_files,
        current_index=0,
        current_percent=0,
        processed_count=0,
        failed_indexes=None
    ):
    failed_indexes = failed_indexes or set()
    files = []

    for i, file in enumerate(audio_files, start=1):
        if i in failed_indexes:
            status = "failed"
            percent = 100

        elif current_index and i == current_index:
            status = "running"
            percent = current_percent

        elif i <= processed_count:
            status = "done"
            percent = 100

        else:
            status = "waiting"
            percent = 0

        files.append({
            "index": i,
            "file_name": Path(file).name,
            "status": status,
            "percent": percent
        })

    return files


def init_progress(job_id, audio_files, **kwargs):
    total_files = len(audio_files)
    lang = kwargs.get("lang", "ko")
    write_progress(job_id, {
        "status": "running",
        "total_files": total_files,
        "current_file_index": 0,
        "processed_count": 0,
        "current_step": "분석 준비 중" if lang == "ko" else "Preparing for analysis" if lang == "en" else "准备分析中",
        "files": make_progress_files(audio_files),
        "result": None,
        "error": None,
        "cancel_requested": False,
        "cancel_reason": None,
        "language": lang
    })


def request_cancel_analysis(job_id, reason="user_navigation"):
    """
    라우터의 cancel_analysis API에서 호출한다.

    1) progress JSON에 cancel_requested=True 저장
    2) 현재 실행 중인 Demucs subprocess가 있으면 terminate/kill
    3) 분석 루프가 check_cancelled()에서 즉시 중단되도록 한다.
    """
    if not job_id:
        return False

    progress = read_progress(job_id)

    if progress is None:
        return False

    progress["status"] = "cancelled"
    progress["current_step"] = "사용자 이동으로 분석이 취소되었습니다."
    progress["cancel_requested"] = True
    progress["cancel_reason"] = reason
    progress["error"] = None

    files = progress.get("files") or []
    for file_item in files:
        if file_item.get("status") == "running":
            file_item["status"] = "failed"
            file_item["percent"] = 100

    progress["files"] = files
    write_progress(job_id, progress)

    with _CURRENT_DEMUCS_PROCESSES_LOCK:
        process = _CURRENT_DEMUCS_PROCESSES.get(job_id)

    if process and process.poll() is None:
        print()
        print("=" * 100)
        print(f"분석 취소 요청 수신: job_id={job_id}, reason={reason}")
        print("실행 중인 Demucs 프로세스를 종료합니다.")
        print("=" * 100)

        terminate_process_tree(process)

    return True


def is_cancel_requested(job_id):
    if not job_id:
        return False

    progress = read_progress(job_id)

    if not progress:
        return False

    return (
        progress.get("cancel_requested") is True
        or progress.get("status") == "cancelled"
    )


def check_cancelled(job_id):
    if is_cancel_requested(job_id):
        raise AnalysisCancelled("분석이 취소되었습니다.")


def write_cancelled_progress(
        job_id,
        audio_files=None,
        current_index=0,
        processed_count=0,
        reason="user_navigation"
    ):
    if not job_id:
        return

    audio_files = audio_files or []
    files = []

    for i, file in enumerate(audio_files, start=1):
        if i <= processed_count:
            status = "done"
            percent = 100
        elif current_index and i == current_index:
            status = "failed"
            percent = 100
        else:
            status = "waiting"
            percent = 0

        files.append({
            "index": i,
            "file_name": Path(file).name,
            "status": status,
            "percent": percent
        })

    write_progress(job_id, {
        "status": "cancelled",
        "total_files": len(audio_files),
        "current_file_index": current_index,
        "processed_count": processed_count,
        "current_step": "사용자 이동으로 분석이 취소되었습니다.",
        "files": files,
        "result": None,
        "error": None,
        "cancel_requested": True,
        "cancel_reason": reason
    })


# =============================
# 1. 원곡 분석
# =============================

def analyze_original_audio_librosa(audio_file, sample_rate=44100, lang="ko"):
    y, sr = librosa.load(audio_file, sr=sample_rate, mono=True)

    duration = librosa.get_duration(y=y, sr=sr)
    minutes = int(duration // 60)
    secs = int(duration % 60)
    duration_text = f"{minutes}:{secs:02d}"

    y_trimmed, _ = librosa.effects.trim(y, top_db=35)

    if len(y_trimmed) == 0:
        y_trimmed = y

    # -----------------------------
    # Key / Chroma
    # -----------------------------
    chroma = librosa.feature.chroma_cqt(y=y_trimmed, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)
    chroma_mean = chroma_mean / (np.linalg.norm(chroma_mean) + 1e-8)

    best_score = -1
    best_key = None
    best_scale = None

    for i in range(12):
        major_profile = np.roll(MAJOR_PROFILE, i)
        minor_profile = np.roll(MINOR_PROFILE, i)

        major_profile = major_profile / np.linalg.norm(major_profile)
        minor_profile = minor_profile / np.linalg.norm(minor_profile)

        major_score = np.dot(chroma_mean, major_profile)
        minor_score = np.dot(chroma_mean, minor_profile)

        if major_score > best_score:
            best_score = major_score
            best_key = NOTE_NAMES[i]
            best_scale = "major"
            scale = "大调" if lang == "zh" else "Major"
        if minor_score > best_score:
            best_score = minor_score
            best_key = NOTE_NAMES[i]
            best_scale = "minor"
            scale = "小调" if lang == "zh" else "minor"

    music_key = f"{best_key} {best_scale}"
    music_key_text = f"{best_key} {scale}"
    # Tempo / Beat
    # -----------------------------
    tempo, beats = librosa.beat.beat_track(y=y_trimmed, sr=sr)
    tempo = float(np.asarray(tempo).flatten()[0])
    tempo = round(tempo)

    onset_env = librosa.onset.onset_strength(y=y_trimmed, sr=sr)
    beat_strength = float(np.mean(onset_env))

    beat_regularity = (
        1.0 / (np.std(np.diff(beats)) + 1e-6)
        if len(beats) > 2
        else 0
    )

    rhythm_pattern = estimate_rhythm_pattern(
        beats=beats,
        onset_env=onset_env,
        sr=sr,
        lang=lang
    )

    # -----------------------------
    # Energy / RMS
    # -----------------------------
    rms = librosa.feature.rms(y=y_trimmed)[0]
    avg_rms = float(np.mean(rms))

    rms_db = 20 * np.log10(avg_rms + 1e-10)
    energy_score = (rms_db + 60) / 60 * 100
    energy_score = max(0, min(100, energy_score))

    if energy_score < 35:
        energy_level = "Low" if lang == "en" else "低" if lang == "zh" else "낮음"
    elif energy_score < 70:
        energy_level = "Medium" if lang == "en" else "中" if lang == "zh" else "중간"
    else:
        energy_level = "High" if lang == "en" else "高" if lang == "zh" else "높음"

    # -----------------------------
    # Spectral Features
    # -----------------------------
    spectral_centroid = librosa.feature.spectral_centroid(y=y_trimmed, sr=sr)[0]
    avg_spectral_centroid = float(np.mean(spectral_centroid))

    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y_trimmed, sr=sr)[0]
    avg_spectral_bandwidth = float(np.mean(spectral_bandwidth))

    spectral_rolloff = librosa.feature.spectral_rolloff(y=y_trimmed, sr=sr)[0]
    avg_spectral_rolloff = float(np.mean(spectral_rolloff))

    spectral_flatness = librosa.feature.spectral_flatness(y=y_trimmed)[0]
    avg_spectral_flatness = float(np.mean(spectral_flatness))

    zero_crossing = librosa.feature.zero_crossing_rate(y=y_trimmed)[0]
    avg_zero_crossing_rate = float(np.mean(zero_crossing))

    stft = np.abs(librosa.stft(y_trimmed))
    stft_norm = stft / (np.sum(stft, axis=0, keepdims=True) + 1e-8)

    spectral_flux = np.sqrt(np.sum(np.diff(stft_norm, axis=1) ** 2, axis=0))
    avg_spectral_flux = float(np.mean(spectral_flux))

    spectral_contrast = librosa.feature.spectral_contrast(y=y_trimmed, sr=sr)
    spectral_contrast_mean = np.mean(spectral_contrast, axis=1)

    # -----------------------------
    # MFCC / Tonnetz
    # -----------------------------
    mfcc = librosa.feature.mfcc(y=y_trimmed, sr=sr, n_mfcc=20)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)

    try:
        harmonic_y = librosa.effects.harmonic(y_trimmed)
        tonnetz = librosa.feature.tonnetz(
            y=harmonic_y,
            sr=sr
        )
        tonnetz_mean = np.mean(tonnetz, axis=1)
    except Exception:
        tonnetz_mean = np.zeros(6)

    # -----------------------------
    # Dynamic Range / HNR
    # -----------------------------
    rms_db_frames = librosa.amplitude_to_db(rms, ref=np.max)
    dynamic_range = (np.percentile(rms_db_frames, 95) - np.percentile(rms_db_frames, 10))

    try:
        snd = parselmouth.Sound(audio_file)
        harmonicity = call(
            snd,
            "To Harmonicity (cc)",
            0.01,
            75,
            0.1,
            1.0
        )
        hnr = call(harmonicity, "Get mean", 0, 0)
    except Exception:
        hnr = None

    # -----------------------------
    # Danceability / Mood / Genre
    # -----------------------------
    tempo_score = 1.0 - min(abs(tempo - 120) / 120, 1.0)

    danceability = (
        0.4 * tempo_score
        + 0.3 * min(beat_strength / 5, 1.0)
        + 0.3 * min(beat_regularity / 10, 1.0)
    ) * 100

    mood = estimate_mood(
        music_key=music_key,
        tempo=tempo,
        energy_score=energy_score,
        spectral_centroid=avg_spectral_centroid,
        danceability=danceability,
        lang=lang
    )

    genre = estimate_genre(
        bpm=tempo,
        energy_score=energy_score,
        spectral_centroid=avg_spectral_centroid,
        zero_crossing_rate=avg_zero_crossing_rate,
        spectral_flatness=avg_spectral_flatness,
        danceability=danceability,
        lang=lang
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
        "beat_strength": round(float(beat_strength), 5),
        "beat_regularity": round(float(beat_regularity), 5),

        "energy_score": round(float(energy_score), 2),
        "energy_level": energy_level,
        "rms": round(avg_rms, 5),

        "genre": genre,
        "mood": mood,

        "spectral_centroid": round(avg_spectral_centroid, 2),
        "spectral_bandwidth": round(avg_spectral_bandwidth, 2),
        "spectral_rolloff": round(avg_spectral_rolloff, 2),
        "spectral_flatness": round(avg_spectral_flatness, 6),
        "spectral_flux": round(avg_spectral_flux, 5),
        "zero_crossing_rate": round(avg_zero_crossing_rate, 6),

        "mfcc_mean": to_float_list(mfcc_mean),
        "mfcc_std": to_float_list(mfcc_std),
        "spectral_contrast_mean": to_float_list(spectral_contrast_mean),
        "chroma_mean": to_float_list(chroma_mean),
        "tonnetz_mean": to_float_list(tonnetz_mean),

        "dynamic_range": round(float(dynamic_range), 2),
        "hnr": round(float(hnr), 2) if hnr is not None else None,
        "danceability": round(float(danceability), 2)
    }


# =============================
# 2. BPM / 장르 / 분위기 / 리듬 정보
# =============================

def get_tempo_info(bpm, lang="ko"):
    if lang not in ("ko", "en", "zh"): lang = "ko"

    if bpm <= 24:
        categories = {"ko": "극도로 느림", "en": "Very Very Slow", "zh": "极其缓慢"}
        descriptions = {
            "ko": "거의 움직임이 느껴지지 않을 정도로 매우 느리게", 
            "en": "Extremely slow, with almost no sense of movement", 
            "zh": "极其缓慢，几乎感觉不到移动"}
        return {"tempo_name": "Larghissimo", "tempo_category": categories[lang], "description": descriptions[lang]}

    elif bpm <= 60:
        categories = {"ko": "매우 느림", "en": "Very Slow", "zh": "非常缓慢"}
        descriptions = {
            "ko": "아주 느리고 폭넓게", 
            "en": "Very slow and broad", 
            "zh": "非常缓慢而宽广"}
        return {"tempo_name": "Largo", "tempo_category": categories[lang], "description": descriptions[lang]}

    elif bpm <= 76:
        categories = {"ko": "느림", "en": "Slow", "zh": "缓慢"}
        descriptions = {
            "ko": "천천히, 편안하게", 
            "en": "Slowly and comfortably", 
            "zh": "缓慢而舒适地"}
        return {"tempo_name": "Adagio", "tempo_category": categories[lang], "description": descriptions[lang]}

    elif bpm <= 108:
        categories = {"ko": "약간 느림", "en": "Moderately Slow", "zh": "中等偏慢"}
        descriptions = {
            "ko": "걷는 속도로", 
            "en": "At a walking pace", 
            "zh": "以步行的速度"}
        return {"tempo_name": "Andante", "tempo_category": categories[lang], "description": descriptions[lang]}

    elif bpm <= 120:
        categories = {"ko": "보통", "en": "Medium", "zh": "中等"}
        descriptions = {
            "ko": "보통 빠르기", 
            "en": "At a moderate speed", 
            "zh": "以中等速度"}
        return {"tempo_name": "Moderato", "tempo_category": categories[lang], "description": descriptions[lang]}

    elif bpm <= 156:
        categories = {"ko": "빠름", "en": "Fast", "zh": "快速"}
        descriptions = {
            "ko": "빠르고 경쾌하게", 
            "en": "Fast and lively", 
            "zh": "快速而欢快地"}
        return {"tempo_name": "Allegro", "tempo_category": categories[lang], "description": descriptions[lang]}

    elif bpm <= 168:
        categories = {"ko": "매우 빠름", "en": "Very Fast", "zh": "非常快速"}
        descriptions = {
            "ko": "생기 있고 아주 빠르게", 
            "en": "Very fast and lively", 
            "zh": "活泼而快速地"}
        return {"tempo_name": "Vivace", "tempo_category": categories[lang], "description": descriptions[lang]}

    elif bpm <= 200:
        categories = {"ko": "매우 빠름", "en": "Very Fast", "zh": "非常快速"}
        descriptions = {
            "ko": "매우 빠르게", 
            "en": "Very fast", 
            "zh": "非常快速地"}
        return {"tempo_name": "Presto", "tempo_category": categories[lang], "description": descriptions[lang]}

    else:
        categories = {"ko": "극도로 빠름", "en": "Extremely Fast", "zh": "极其快速"}
        descriptions = {
            "ko": "가능한 한 아주 빠르게", 
            "en": "As fast as possible", 
            "zh": "尽可能快地"}
        return {"tempo_name": "Prestissimo", "tempo_category": categories[lang], "description": descriptions[lang]}

def estimate_genre(
        bpm,
        energy_score,
        spectral_centroid=None,
        zero_crossing_rate=None,
        spectral_flatness=None,
        danceability=None,
        lang="ko"
    ):
    if lang not in ("ko", "en", "zh"):
        lang = "ko"

    genre_text = {
        "ballad": {
            "ko": "발라드 / 어쿠스틱 계열",
            "en": "Ballad / Acoustic-like",
            "zh": "抒情 / 原声风格"
        },
        "pop": {
            "ko": "팝 계열",
            "en": "Pop-like",
            "zh": "流行风格"
        },
        "dance": {
            "ko": "댄스 / EDM 계열",
            "en": "Dance / EDM-like",
            "zh": "舞曲 / EDM风格"
        },
        "rock": {
            "ko": "록 / 일렉트로닉 계열",
            "en": "Rock / Electronic-like",
            "zh": "摇滚 / 电子风格"
        },
        "jazz": {
            "ko": "재즈 / 어쿠스틱 계열",
            "en": "Jazz / Acoustic-like",
            "zh": "爵士 / 原声风格"
        },
        "mixed": {
            "ko": "혼합 / 알 수 없음",
            "en": "Mixed / Unknown",
            "zh": "混合 / 未知"
        }
    }

    scores = {
        "ballad": 0,
        "pop": 0,
        "dance": 0,
        "rock": 0,
        "jazz": 0,
        "mixed": 0
    }

    # Dance / EDM
    if bpm >= 120:
        scores["dance"] += 2
    if energy_score >= 70:
        scores["dance"] += 2
    if danceability is not None and danceability >= 55:
        scores["dance"] += 1
    if spectral_flatness is not None and spectral_flatness >= 0.03:
        scores["dance"] += 1

    # Pop
    if 90 <= bpm <= 130:
        scores["pop"] += 2
    if 45 <= energy_score <= 75:
        scores["pop"] += 2
    if danceability is not None and 35 <= danceability <= 65:
        scores["pop"] += 1

    # Ballad / Acoustic
    if bpm < 95:
        scores["ballad"] += 2
    if energy_score < 60:
        scores["ballad"] += 2
    if spectral_centroid is not None and spectral_centroid < 2200:
        scores["ballad"] += 1
    if zero_crossing_rate is not None and zero_crossing_rate < 0.05:
        scores["ballad"] += 1

    # Rock / Electronic
    if bpm >= 130:
        scores["rock"] += 1
    if energy_score >= 65:
        scores["rock"] += 1
    if spectral_centroid is not None and spectral_centroid >= 2500:
        scores["rock"] += 1
    if zero_crossing_rate is not None and zero_crossing_rate >= 0.08:
        scores["rock"] += 1

    # Jazz / Acoustic
    if spectral_centroid is not None and spectral_centroid < 1800:
        scores["jazz"] += 1
    if energy_score < 65:
        scores["jazz"] += 1

    best_genre = max(scores, key=scores.get)

    if scores[best_genre] == 0:
        best_genre = "mixed"

    return genre_text[best_genre][lang]


def estimate_rhythm_pattern(beats, onset_env, sr, lang="ko"):
    if lang not in ("ko", "en", "zh"):
        lang = "ko"

    rhythm_text = {
        "not_detected": {
            "ko": "리듬이 명확하게 감지되지 않음",
            "en": "Rhythm not clearly detected",
            "zh": "未能清晰检测到节奏"
        },
        "strong_steady": {
            "ko": "강하고 일정한 비트",
            "en": "Strong and steady beat",
            "zh": "强烈而稳定的节拍"
        },
        "steady": {
            "ko": "일정한 리듬",
            "en": "Steady rhythm",
            "zh": "稳定的节奏"
        },
        "moderate_variation": {
            "ko": "적당한 리듬 변화",
            "en": "Moderate rhythmic variation",
            "zh": "适度的节奏变化"
        },
        "irregular_expressive": {
            "ko": "불규칙하거나 표현적인 리듬",
            "en": "Irregular or expressive rhythm",
            "zh": "不规则或富有表现力的节奏"
        }
    }

    if beats is None or len(beats) < 3:
        return rhythm_text["not_detected"][lang]

    beat_times = librosa.frames_to_time(beats, sr=sr)
    beat_intervals = np.diff(beat_times)

    if len(beat_intervals) == 0:
        return rhythm_text["not_detected"][lang]

    interval_mean = float(np.mean(beat_intervals))
    interval_std = float(np.std(beat_intervals))
    beat_variation = interval_std / (interval_mean + 1e-8)

    beat_strength = float(np.mean(onset_env))

    if beat_variation < 0.08 and beat_strength >= 1.5:
        return rhythm_text["strong_steady"][lang]

    elif beat_variation < 0.12:
        return rhythm_text["steady"][lang]

    elif beat_variation < 0.2:
        return rhythm_text["moderate_variation"][lang]

    else:
        return rhythm_text["irregular_expressive"][lang]


def estimate_mood(
        music_key,
        tempo,
        energy_score,
        spectral_centroid,
        danceability,
        lang="ko"
    ):
    if lang not in ("ko", "en", "zh"):
        lang = "ko"

    mood_text = {
        "melancholic": {
            "ko": "우울 / 감성",
            "en": "Melancholic / Emotional",
            "zh": "忧郁 / 感性"
        },
        "bright": {
            "ko": "밝음 / 활기참",
            "en": "Bright / Energetic",
            "zh": "明亮 / 充满活力"
        },
        "powerful": {
            "ko": "강렬 / 강함",
            "en": "Powerful / Intense",
            "zh": "强劲 / 强烈"
        },
        "calm": {
            "ko": "차분 / 부드러움",
            "en": "Calm / Soft",
            "zh": "平静 / 柔和"
        },
        "dramatic": {
            "ko": "극적 / 감성",
            "en": "Dramatic / Emotional",
            "zh": "戏剧性 / 感性"
        },
        "groovy": {
            "ko": "그루비 / 기분 상승",
            "en": "Groovy / Uplifting",
            "zh": "富有律动感 / 振奋"
        },
        "neutral": {
            "ko": "중립 / 균형",
            "en": "Neutral / Balanced",
            "zh": "中性 / 平衡"
        }
    }

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

    return mood_text[mood_key][lang]


# =============================
# 3. Demucs 보컬 분리
# =============================

def extract_percent_from_text(text):
    matches = re.findall(r"(\d{1,3})\s*%", text)

    if not matches:
        return None

    percent = int(matches[-1])
    percent = max(0, min(100, percent))

    return percent


def print_single_line_progress(label, percent):
    bar_length = 30
    percent = max(0, min(100, int(percent)))

    filled_length = int(bar_length * percent / 100)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    print(
        f"\r{label} [{bar}] {percent:3d}%",
        end="",
        flush=True
    )


def run_demucs_with_percent_bar(command, env, log_path, progress_callback=None, job_id=None):
    """
    Demucs 출력은 로그 파일에 저장하고,
    터미널에는 한 줄짜리 퍼센트 진행 막대만 표시한다.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "percent": 0,
        "last_rendered": -1,
        "reader_done": False
    }

    lock = threading.Lock()

    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write("\n" + "=" * 100 + "\n")
        log_file.write(f"Demucs started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write("Command:\n")
        log_file.write(" ".join(command) + "\n")
        log_file.write("=" * 100 + "\n")
        log_file.flush()

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            start_new_session=True
        )

        if job_id:
            with _CURRENT_DEMUCS_PROCESSES_LOCK:
                _CURRENT_DEMUCS_PROCESSES[job_id] = process

        def read_demucs_output():
            try:
                for line in iter(process.stdout.readline, ""):
                    log_file.write(line)
                    log_file.flush()

                    parsed_percent = extract_percent_from_text(line)

                    if parsed_percent is not None:
                        with lock:
                            state["percent"] = max(
                                state["percent"],
                                min(parsed_percent, 99)
                            )
            finally:
                with lock:
                    state["reader_done"] = True

        reader_thread = threading.Thread(
            target=read_demucs_output,
            daemon=True
        )
        reader_thread.start()

        fallback_percent = 0
        print_single_line_progress("보컬 분리", 0)

        while process.poll() is None:
            if is_cancel_requested(job_id):
                print()
                print("=" * 100)
                print(f"Demucs 취소 요청 감지: job_id={job_id}")
                print("=" * 100)

                terminate_process_tree(process)

                reader_thread.join(timeout=2)

                if job_id:
                    with _CURRENT_DEMUCS_PROCESSES_LOCK:
                        if _CURRENT_DEMUCS_PROCESSES.get(job_id) is process:
                            _CURRENT_DEMUCS_PROCESSES.pop(job_id, None)

                raise AnalysisCancelled("분석이 취소되었습니다.")

            with lock:
                real_percent = state["percent"]

            if real_percent > 0:
                display_percent = real_percent
            else:
                fallback_percent = min(fallback_percent + 1, 95)
                display_percent = fallback_percent

            with lock:
                should_render = display_percent != state["last_rendered"]
                state["last_rendered"] = display_percent

            if should_render:
                print_single_line_progress("보컬 분리", display_percent)

                if progress_callback:
                    progress_callback(display_percent)

            time.sleep(0.35)

        reader_thread.join(timeout=2)

        if job_id:
            with _CURRENT_DEMUCS_PROCESSES_LOCK:
                if _CURRENT_DEMUCS_PROCESSES.get(job_id) is process:
                    _CURRENT_DEMUCS_PROCESSES.pop(job_id, None)

        if is_cancel_requested(job_id):
            raise AnalysisCancelled("분석이 취소되었습니다.")

        if process.returncode != 0:
            print_single_line_progress("보컬 분리 실패", 100)
            print()
            print(f"Demucs 오류 로그 확인: {log_path.resolve()}")

            raise subprocess.CalledProcessError(
                process.returncode,
                command
            )

        print_single_line_progress("보컬 분리", 100)
        print()

        if progress_callback:
            progress_callback(100)


def separate_vocals(audio_file, progress_callback=None, job_id=None):
    audio_path = Path(audio_file)

    if not audio_path.exists():
        raise FileNotFoundError(f"Not found: {audio_file}")

    check_cancelled(job_id)

    output_dir = SEPARATED_DIR
    song_name = audio_path.stem

    vocals_path = output_dir / "htdemucs" / song_name / "vocals.wav"
    no_vocals_path = output_dir / "htdemucs" / song_name / "no_vocals.wav"

    if vocals_path.exists() and no_vocals_path.exists():
        print_single_line_progress("보컬 분리 캐시 사용", 100)
        print()

        if progress_callback:
            progress_callback(100)

        check_cancelled(job_id)

        return {
            "vocals_path": str(vocals_path),
            "no_vocals_path": str(no_vocals_path)
        }

    command = [
        sys.executable,
        "-m",
        "demucs",
        "--two-stems=vocals",
        "-o",
        str(output_dir),
        str(audio_path)
    ]

    env = os.environ.copy()
    env["SSL_CERT_FILE"] = certifi.where()
    env["REQUESTS_CA_BUNDLE"] = certifi.where()

    log_path = output_dir / "demucs_logs" / f"{song_name}_demucs.log"

    run_demucs_with_percent_bar(
        command=command,
        env=env,
        log_path=log_path,
        progress_callback=progress_callback,
        job_id=job_id
    )

    print("_" * 100)

    if not vocals_path.exists():
        raise FileNotFoundError(
            f"Demucs 보컬 파일을 찾을 수 없습니다: {vocals_path}"
        )

    if not no_vocals_path.exists():
        raise FileNotFoundError(
            f"Demucs 배경음악 파일을 찾을 수 없습니다: {no_vocals_path}"
        )

    check_cancelled(job_id)

    return {
        "vocals_path": str(vocals_path),
        "no_vocals_path": str(no_vocals_path)
    }


# =============================
# 4. 보컬 피치 분석
# =============================

def analyze_pitch_torchcrepe(vocal_file):
    sr = 16000
    audio, _ = librosa.load(vocal_file, sr=sr, mono=True)

    audio = torch.tensor(audio).float().unsqueeze(0)

    hop_length = 640

    print("torchcrepe pitch analysis starting...")

    pitch, periodicity = torchcrepe.predict(
        audio,
        sr,
        hop_length,
        fmin=librosa.note_to_hz("A2"),
        fmax=librosa.note_to_hz("C6"),
        model="tiny",
        batch_size=2048,
        device="cpu",
        return_periodicity=True
    )

    print("torchcrepe pitch analysis completed")

    pitch = pitch.squeeze().numpy()
    periodicity = periodicity.squeeze().numpy()

    valid = (
        (pitch > 0)
        & (periodicity > 0.7)
    )

    valid_pitch = pitch[valid]

    if len(valid_pitch) == 0:
        return None

    midi = np.round(librosa.hz_to_midi(valid_pitch)).astype(int)

    lowest_midi = int(np.percentile(midi, 10))
    highest_midi = int(np.percentile(midi, 98))

    semitones = highest_midi - lowest_midi

    result = {
        "lowest_pitch_hz": round(librosa.midi_to_hz(lowest_midi)),
        "lowest_note": librosa.midi_to_note(lowest_midi),
        "highest_pitch_hz": round(librosa.midi_to_hz(highest_midi)),
        "highest_note": librosa.midi_to_note(highest_midi),
        "pitch_range_semitones": int(semitones),
        "pitch_range_octaves": round(semitones / 12, 2)
    }

    return result


# =============================
# 5. AST 모델 / 악기 분석
# =============================

def load_ast_model():
    model_name = "MIT/ast-finetuned-audioset-10-10-0.4593"

    print("AST model loading...")
    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModelForAudioClassification.from_pretrained(model_name)
    model.eval()
    print("AST model loaded")

    return processor, model


def detect_background_instruments_ast(background_file, processor, model, threshold=0.008, top_n=10, lang="ko"):
    if lang not in ("ko", "en", "zh"): lang = "ko"

    audio, _ = librosa.load(background_file, sr=16000, mono=True)
    inputs = processor(audio, sampling_rate=16000, return_tensors="pt")

    with torch.no_grad(): outputs = model(**inputs)

    scores = torch.sigmoid(outputs.logits[0])
    id2label = model.config.id2label

    instrument_groups = {
        "drums_percussion": ["drum", "drum kit", "snare drum", "bass drum", "cymbal", 
                             "percussion", "wood block", "cowbell", "hi-hat", "tabla", 
                             "bongo", "conga"],
        "electronic": ["synthesizer", "drum machine", "sampler"],
        "piano_keyboard": ["piano", "electric piano", "keyboard"],
        "guitar": ["guitar", "electric guitar", "acoustic guitar"],
        "bass": ["bass guitar", "double bass", "electric bass"],
        "strings": ["violin", "viola", "cello", "string", "harp"],
        "brass": ["trumpet", "trombone", "brass", "horn"],
        "woodwinds": ["flute", "clarinet", "saxophone", "oboe"],
        "organ_accordion": ["organ", "accordion"]
    }

    instrument_text = {
        "drums_percussion": {"ko": "드럼 / 타악기", "en": "Drums / Percussion", "zh": "鼓 / 打击乐器"},
        "electronic": {"ko": "전자 악기", "en": "Electronic Instruments", "zh": "电子乐器"},
        "piano_keyboard": {"ko": "피아노 / 키보드", "en": "Piano / Keyboard", "zh": "钢琴 / 键盘"},
        "guitar": {"ko": "Guitar", "en": "Guitar", "zh": "吉他"},
        "bass": {"ko": "Bass", "en": "Bass", "zh": "贝斯"},
        "strings": {"ko": "현악기", "en": "Strings", "zh": "弦乐器"},
        "brass": {"ko": "금관악기", "en": "Brass", "zh": "铜管乐器"},
        "woodwinds": {"ko": "목관악기", "en": "Woodwinds", "zh": "木管乐器"},
        "organ_accordion": {"ko": "오르간 / 아코디언", "en": "Organ / Accordion", "zh": "风琴 / 手风琴"}
    }

    detected_groups = {}
    top_scores, top_indices = torch.topk(scores, min(30, len(scores)))

    for score, idx in zip(top_scores, top_indices):
        label = id2label[int(idx)]
        score_value = float(score)
        label_lower = label.lower()

        for group_key, keywords in instrument_groups.items():
            if not any(keyword in label_lower for keyword in keywords): continue

            if group_key not in detected_groups:
                detected_groups[group_key] = {
                    "instrument": instrument_text[group_key][lang],
                    "instrument_key": group_key,
                    "score": score_value,
                    "percentage": round(score_value * 100, 1),
                    "matched_labels": [label]
                }
            else:
                if score_value > detected_groups[group_key]["score"]:
                    detected_groups[group_key]["score"] = score_value
                    detected_groups[group_key]["percentage"] = round(score_value * 100, 1)

                detected_groups[group_key]["matched_labels"].append(label)

    detected = [info for info in detected_groups.values() if info["score"] >= threshold]
    detected = sorted(detected, key=lambda item: item["score"], reverse=True)[:top_n]

    return {"instrument_count": len(detected), "instruments": detected}


# =============================
# 6. 곡 1개 분석
# =============================

def analyze_one_music_file(
        audio_file,
        ast_processor,
        ast_model,
        sample_rate=44100,
        file_index=None,
        progress_callback=None,
        job_id=None,
        **kwargs
    ):
    music_name = Path(audio_file).stem
    lang = kwargs.get("lang", "ko")
    if lang not in UPDATE_STEP_TEXT:
        lang = "ko"
    step_text = UPDATE_STEP_TEXT[lang]

    print("\n" + "=" * 100)
    if file_index is not None: 
        print(f"{file_index}. {music_name}")
    else:
        print(music_name)
    print("=" * 100)

    total_start = time.perf_counter()

    check_cancelled(job_id)

    def update_step(percent, step):
        if progress_callback:
            progress_callback(percent, step)

    update_step(10, step_text["original_analyzing"])

    start = time.perf_counter()
    original_info = analyze_original_audio_librosa(audio_file, sample_rate, lang)
    original_time = time.perf_counter() - start

    check_cancelled(job_id)

    update_step(25, step_text["original_completed"])

    print(f"Duration: {original_info['duration']} sec")
    print(f"Duration (min:sec): {original_info['duration_text']}")
    print(f"Key: {original_info['key']}")
    print(f"Key Confidence: {original_info['key_confidence']}")

    tempo = original_info["tempo"]
    tempo_info = get_tempo_info(tempo,lang)

    print(f"Tempo: {tempo} bpm")
    print(f"Tempo Name: {tempo_info['tempo_name']}")
    print(f"Tempo Category: {tempo_info['tempo_category']}")
    print(f"Description: {tempo_info['description']}")
    print(f"Rhythm Pattern: {original_info['rhythm_pattern']}")
    print(f"Beat Count: {original_info['beat_count']}")
    print(f"Beat Strength: {original_info['beat_strength']}")
    print(f"Beat Regularity: {original_info['beat_regularity']}")

    print("-" * 100)
    print(f"Energy Score: {original_info['energy_score']}")
    print(f"Energy Level: {original_info['energy_level']}")
    print(f"RMS: {original_info['rms']}")
    print(f"Genre: {original_info['genre']}")
    print(f"Mood: {original_info['mood']}")
    print(f"Spectral Centroid: {original_info['spectral_centroid']} Hz")
    print(f"Spectral Bandwidth: {original_info['spectral_bandwidth']}")
    print(f"Spectral Rolloff: {original_info['spectral_rolloff']}")
    print(f"Spectral Flatness: {original_info['spectral_flatness']}")
    print(f"Spectral Flux: {original_info['spectral_flux']}")
    print(f"Zero Crossing Rate: {original_info['zero_crossing_rate']}")
    print(f"Dynamic Range: {original_info['dynamic_range']} dB")
    print(f"Harmonic-to-Noise Ratio: {original_info['hnr']} dB")
    print(f"Danceability: {original_info['danceability']}")
    print("-" * 100)

    update_step(35, step_text["separating"])

    def demucs_progress_callback(demucs_percent):
        mapped_percent = 35 + int((demucs_percent / 100) * 20)
        mapped_percent = max(35, min(55, mapped_percent))

        update_step(mapped_percent, step_text["separating_percent"]+f" ({demucs_percent}%)")
        # f"{file_index}번째 음악 오디오 보컬/배경음악 분리 중 ({demucs_percent}%)"

    start = time.perf_counter()
    separated_files = separate_vocals(
        audio_file,
        progress_callback=demucs_progress_callback,
        job_id=job_id
    )

    check_cancelled(job_id)

    vocal_file = separated_files["vocals_path"]
    background_file = separated_files["no_vocals_path"]

    separation_time = time.perf_counter() - start

    update_step(55, step_text["separation_completed"])

    update_step(65, step_text["pitch_analyzing"])

    start = time.perf_counter()
    pitch_range = analyze_pitch_torchcrepe(vocal_file)
    pitch_time = time.perf_counter() - start

    check_cancelled(job_id)

    update_step(75, step_text["pitch_completed"])

    if pitch_range is not None:
        print(f"Lowest Vocal Pitch: {pitch_range['lowest_pitch_hz']} Hz")
        print(f"Lowest Vocal Note: {pitch_range['lowest_note']}")
        print(f"Highest Vocal Pitch: {pitch_range['highest_pitch_hz']} Hz")
        print(f"Highest Vocal Note: {pitch_range['highest_note']}")
        print(f"Vocal Pitch Range: {pitch_range['pitch_range_semitones']} semitones")
        print(f"Vocal Pitch Range Octaves: {pitch_range['pitch_range_octaves']} octaves")
    else:
        print("Vocal Pitch: 분석 가능한 보컬 피치를 찾지 못했습니다.")

    print("-" * 100)

    update_step(85, step_text["instrument_analyzing"])

    start = time.perf_counter()
    instrument_result = detect_background_instruments_ast(
        background_file,
        ast_processor,
        ast_model,
        threshold=0.008,
        top_n=10,
        lang=lang
    )
    instrument_time = time.perf_counter() - start

    check_cancelled(job_id)

    update_step(95, step_text["saving"])

    print(f"Background Instrument Count: {instrument_result['instrument_count']}")
    print("Background Instruments:")
    print("-" * 100)

    for item in instrument_result["instruments"]:
        print(
            f"{item['instrument']}: {item['percentage']}% "
            f"({', '.join(item['matched_labels'])})"
        )

    total_time = time.perf_counter() - total_start

    result = {
        "file_info": {
            "file_name": Path(audio_file).name,
            "file_path": str(audio_file),
            "duration": round(original_info["duration"], 2),
            "duration_text": original_info["duration_text"]
        },

        "original_audio_analysis": {
            "key": original_info["key"],
            "key_confidence": original_info["key_confidence"],
            "key_method": original_info["key_method"],

            "tempo": original_info["tempo"],
            "tempo_name": tempo_info["tempo_name"],
            "tempo_category": tempo_info["tempo_category"],
            "tempo_description": tempo_info["description"],

            "rhythm_pattern": original_info["rhythm_pattern"],
            "beat_count": original_info["beat_count"],
            "beat_strength": original_info["beat_strength"],
            "beat_regularity": original_info["beat_regularity"],

            "energy_score": original_info["energy_score"],
            "energy_level": original_info["energy_level"],
            "rms": original_info["rms"],
            "genre": original_info["genre"],
            "mood": original_info["mood"],

            "spectral_centroid": original_info["spectral_centroid"],
            "spectral_bandwidth": original_info["spectral_bandwidth"],
            "spectral_rolloff": original_info["spectral_rolloff"],
            "spectral_flatness": original_info["spectral_flatness"],
            "spectral_flux": original_info["spectral_flux"],
            "zero_crossing_rate": original_info["zero_crossing_rate"],

            "mfcc_mean": original_info["mfcc_mean"],
            "mfcc_std": original_info["mfcc_std"],
            "spectral_contrast_mean": original_info["spectral_contrast_mean"],
            "chroma_mean": original_info["chroma_mean"],
            "tonnetz_mean": original_info["tonnetz_mean"],

            "dynamic_range": original_info["dynamic_range"],
            "harmonic_to_noise_ratio": original_info["hnr"],
            "danceability": original_info["danceability"]
        },

        "vocal_pitch_analysis": pitch_range,

        "background_instrument_analysis": {
            "instrument_count": instrument_result["instrument_count"],
            "instruments": instrument_result["instruments"]
        },

        "analysis_time_summary": {
            "original_audio_analysis_time": round(original_time),
            "vocal_separation_time": round(separation_time),
            "vocal_pitch_analysis_time": round(pitch_time),
            "background_instrument_analysis_time": round(instrument_time),
            "total_analysis_time": round(total_time)
        }
    }

    result_dir = Path(vocal_file).parent
    json_file_name = Path(audio_file).stem + "_analysis.json"
    json_path = result_dir / json_file_name

    check_cancelled(job_id)

    save_json_result(result, json_path)

    track_id = save_music_analysis_to_db(result)
    result["db_track_id"] = track_id

    if job_id:
        mark_analysis_job_success(job_id, track_id)

    update_step(100, step_text["analysis_completed"])

    print(f"Analysis result saved: {json_path.resolve()}")
    print(f"Analysis result saved to DB. track_id={track_id}")

    return result


# =============================
# 7. 실행 함수
# =============================

_AST_PROCESSOR = None
_AST_MODEL = None


def get_ast_model():
    global _AST_PROCESSOR, _AST_MODEL

    if _AST_PROCESSOR is None or _AST_MODEL is None:
        _AST_PROCESSOR, _AST_MODEL = load_ast_model()

    return _AST_PROCESSOR, _AST_MODEL


def run_uploaded_analysis(audio_file_paths, sample_rate=44100, job_id=None, **kwargs):
    if isinstance(audio_file_paths, str):
        audio_files = [audio_file_paths]
    else:
        audio_files = audio_file_paths

    print("분석할 파일 개수:", len(audio_files))
    print("분석할 파일 목록:", audio_files)

    return music_audio_analysis(
        audio_files,
        sample_rate,
        job_id=job_id,
        lang=kwargs.get("lang", "ko")
    )


def music_audio_analysis(audio_files, sample_rate=44100, job_id=None, **kwargs):
    all_results = []
    failed_indexes = set()

    program_start = time.perf_counter()

    ast_processor, ast_model = get_ast_model()

    total_files = len(audio_files)
    processed_count = 0
    lang = kwargs.get("lang", "ko")

    init_progress(job_id, audio_files,**kwargs)
    check_cancelled(job_id)

    for index, audio_file in enumerate(audio_files, start=1):
        check_cancelled(job_id)

        result = None
        was_cancelled = False

        def update_current_file(percent, step):
            check_cancelled(job_id)

            write_progress(job_id, {
                "status": "running",
                "total_files": total_files,
                "current_file_index": index,
                "processed_count": processed_count,
                "current_step": step,
                "files": make_progress_files(
                    audio_files,
                    current_index=index,
                    current_percent=percent,
                    processed_count=processed_count,
                    failed_indexes=failed_indexes
                ),
                "result": None,
                "error": None,
                "cancel_requested": False,
                "cancel_reason": None
            })

        try:
            update_current_file(
                5,
                f"{index}번째 음악 오디오 분석 시작"
            )

            result = analyze_one_music_file(
                audio_file,
                ast_processor,
                ast_model,
                sample_rate,
                file_index=index,
                progress_callback=update_current_file,
                job_id=job_id,
                lang=lang
            )

            all_results.append(result)

        except AnalysisCancelled:
            was_cancelled = True

            write_cancelled_progress(
                job_id,
                audio_files=audio_files,
                current_index=index,
                processed_count=processed_count
            )

            print()
            print("=" * 100)
            print(f"분석이 취소되었습니다. job_id={job_id}")
            print("=" * 100)

            return {
                "cancelled": True,
                "job_id": job_id,
                "total_file_count": len(all_results),
                "results": all_results
            }

        except Exception as e:
            failed_indexes.add(index)

            if job_id:
                mark_analysis_job_failed(job_id, str(e))

            print("\n" + "!" * 100)
            print(f"분석 실패: {audio_file}")
            print(f"Error: {e}")
            print("!" * 100)

            write_progress(job_id, {
                "status": "running",
                "total_files": total_files,
                "current_file_index": index,
                "processed_count": processed_count,
                "current_step": f"{index}번째 음악 오디오 분석 실패",
                "files": make_progress_files(
                    audio_files,
                    current_index=index,
                    current_percent=100,
                    processed_count=processed_count,
                    failed_indexes=failed_indexes
                ),
                "result": None,
                "error": str(e),
                "cancel_requested": False,
                "cancel_reason": None
            })

        finally:
            if not was_cancelled:
                processed_count += 1

                write_progress(job_id, {
                    "status": "running",
                    "total_files": total_files,
                    "current_file_index": 0,
                    "processed_count": processed_count,
                    "current_step": f"{index}번째 음악 오디오 분석 완료"
                    if result is not None
                    else f"{index}번째 음악 오디오 분석 실패",
                    "files": make_progress_files(
                        audio_files,
                        current_index=0,
                        current_percent=0,
                        processed_count=processed_count,
                        failed_indexes=failed_indexes
                    ),
                    "result": None,
                    "error": None if result is not None else "일부 파일 분석 실패",
                    "cancel_requested": False,
                    "cancel_reason": None
                })

                print("\n" + "=" * 100)
                print("Progress Summary")
                print("-" * 100)
                print(f"Progress: {processed_count}/{total_files}")

                if result is not None:
                    time_info = result["analysis_time_summary"]

                    print(f"Original Audio Analysis: {time_info['original_audio_analysis_time']} sec")
                    print(f"Vocal Separation: {time_info['vocal_separation_time']} sec")
                    print(f"Vocal Pitch Analysis: {time_info['vocal_pitch_analysis_time']} sec")
                    print(f"Background Instrument Analysis: {time_info['background_instrument_analysis_time']} sec")
                    print(f"Current File Total Analysis Time: {time_info['total_analysis_time']} sec")
                else:
                    print("Analysis Time Summary: 분석 실패로 표시할 수 없습니다.")

    if is_cancel_requested(job_id):
        write_cancelled_progress(
            job_id,
            audio_files=audio_files,
            current_index=0,
            processed_count=processed_count
        )

        return {
            "cancelled": True,
            "job_id": job_id,
            "total_file_count": len(all_results),
            "results": all_results
        }

    total_music_duration = sum(
        result["file_info"]["duration"]
        for result in all_results
    )

    music_minutes = int(total_music_duration // 60)
    music_seconds = int(total_music_duration % 60)

    program_total_time = time.perf_counter() - program_start
    minutes = int(program_total_time // 60)
    seconds = int(program_total_time % 60)

    summary_result = {
        "total_file_count": len(all_results),

        "total_music_duration": {
            "seconds": round(total_music_duration, 2),
            "text": format_duration_text(total_music_duration, lang)
        },

        "total_program_execution_time": {
            "seconds": round(program_total_time, 2),
            "text": format_duration_text(program_total_time, lang)
        },

        "results": all_results
    }

    summary_json_path = ANALYSIS_RESULTS_DIR / "all_music_analysis_summary.json"
    save_json_result(summary_result, summary_json_path)

    write_progress(job_id, {
        "status": "completed",
        "total_files": total_files,
        "current_file_index": 0,
        "processed_count": processed_count,
        "current_step": "전체 분석 완료" if lang == "ko" else "Analysis Completed" if lang == "en" else "分析完成",
        "files": make_progress_files(
            audio_files,
            current_index=0,
            current_percent=0,
            processed_count=total_files,
            failed_indexes=failed_indexes
        ),
        "result": summary_result,
        "error": None,
        "cancel_requested": False,
        "cancel_reason": None
    })

    print("\n" + "=" * 100)
    print("Final Summary")
    print("=" * 100)
    print(f"Total File Count: {summary_result['total_file_count']}")
    print(
        f"Total Music Duration: "
        f"{summary_result['total_music_duration']['seconds']} sec "
        f"({summary_result['total_music_duration']['text']})"
    )
    print(
        f"Total Program Execution Time: "
        f"{summary_result['total_program_execution_time']['seconds']} sec "
        f"({summary_result['total_program_execution_time']['text']})"
    )
    print(f"Summary JSON Path: {summary_json_path.resolve()}")
    print("=" * 100)

    return summary_result


if __name__ == "__main__":
    print("이 파일은 Flask 업로드 분석 서비스에서 import해서 사용하는 분석 로직 파일입니다.")
    print("직접 실행하려면 music_audio_analysis([파일경로1, 파일경로2]) 형태로 호출하세요.")
