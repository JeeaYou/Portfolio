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

from .music_db_service import (
    save_music_analysis_to_db,
    mark_analysis_job_success,
    mark_analysis_job_failed,
)


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


class AnalysisCancelled(Exception):
    """사용자가 화면 이동/Home 클릭 등으로 분석을 취소한 경우 사용한다."""
    pass


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


def init_progress(job_id, audio_files):
    total_files = len(audio_files)

    write_progress(job_id, {
        "status": "running",
        "total_files": total_files,
        "current_file_index": 0,
        "processed_count": 0,
        "current_step": "분석 준비 중",
        "files": make_progress_files(audio_files),
        "result": None,
        "error": None,
        "cancel_requested": False,
        "cancel_reason": None
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

def analyze_original_audio_librosa(audio_file, sample_rate=44100):
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

        if minor_score > best_score:
            best_score = minor_score
            best_key = NOTE_NAMES[i]
            best_scale = "minor"

    music_key = f"{best_key} {best_scale}"

    # -----------------------------
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
        tempo=tempo,
        beats=beats,
        onset_env=onset_env,
        sr=sr
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
        energy_level = "Low Energy"
    elif energy_score < 70:
        energy_level = "Medium Energy"
    else:
        energy_level = "High Energy"

    # -----------------------------
    # Spectral Features
    # -----------------------------
    spectral_centroid = librosa.feature.spectral_centroid(
        y=y_trimmed,
        sr=sr
    )[0]
    avg_spectral_centroid = float(np.mean(spectral_centroid))

    spectral_bandwidth = librosa.feature.spectral_bandwidth(
        y=y_trimmed,
        sr=sr
    )[0]
    avg_spectral_bandwidth = float(np.mean(spectral_bandwidth))

    spectral_rolloff = librosa.feature.spectral_rolloff(
        y=y_trimmed,
        sr=sr
    )[0]
    avg_spectral_rolloff = float(np.mean(spectral_rolloff))

    spectral_flatness = librosa.feature.spectral_flatness(
        y=y_trimmed
    )[0]
    avg_spectral_flatness = float(np.mean(spectral_flatness))

    zero_crossing = librosa.feature.zero_crossing_rate(
        y_trimmed
    )[0]
    avg_zero_crossing_rate = float(np.mean(zero_crossing))

    stft = np.abs(librosa.stft(y_trimmed))
    stft_norm = stft / (np.sum(stft, axis=0, keepdims=True) + 1e-8)

    spectral_flux = np.sqrt(
        np.sum(np.diff(stft_norm, axis=1) ** 2, axis=0)
    )
    avg_spectral_flux = float(np.mean(spectral_flux))

    spectral_contrast = librosa.feature.spectral_contrast(
        y=y_trimmed,
        sr=sr
    )
    spectral_contrast_mean = np.mean(spectral_contrast, axis=1)

    # -----------------------------
    # MFCC / Tonnetz
    # -----------------------------
    mfcc = librosa.feature.mfcc(
        y=y_trimmed,
        sr=sr,
        n_mfcc=20
    )
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
    dynamic_range = (
        np.percentile(rms_db_frames, 95)
        - np.percentile(rms_db_frames, 10)
    )

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
        danceability=danceability
    )

    genre = estimate_genre(
        bpm=tempo,
        energy_score=energy_score,
        spectral_centroid=avg_spectral_centroid,
        zero_crossing_rate=avg_zero_crossing_rate,
        spectral_flatness=avg_spectral_flatness,
        danceability=danceability
    )

    return {
        "duration": round(duration, 2),
        "duration_text": duration_text,

        "key": music_key,
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

def get_tempo_info(bpm):
    if bpm <= 24:
        return {
            "tempo_name": "Larghissimo",
            "tempo_category": "Very Very Slow",
            "description": "almost no movement very slow"
        }
    elif bpm <= 60:
        return {
            "tempo_name": "Largo",
            "tempo_category": "Very Slow",
            "description": "Very slow"
        }
    elif bpm <= 76:
        return {
            "tempo_name": "Adagio",
            "tempo_category": "Slow",
            "description": "천천히, 편안하게"
        }
    elif bpm <= 108:
        return {
            "tempo_name": "Andante",
            "tempo_category": "Moderately Slow",
            "description": "걷는 속도"
        }
    elif bpm <= 120:
        return {
            "tempo_name": "Moderato",
            "tempo_category": "Medium",
            "description": "보통 빠르기"
        }
    elif bpm <= 156:
        return {
            "tempo_name": "Allegro",
            "tempo_category": "Fast",
            "description": "빠르고 경쾌하게"
        }
    elif bpm <= 168:
        return {
            "tempo_name": "Vivace",
            "tempo_category": "Very Fast",
            "description": "생기 있고 아주 빠르게"
        }
    elif bpm <= 200:
        return {
            "tempo_name": "Presto",
            "tempo_category": "Very Fast",
            "description": ""
        }
    else:
        return {
            "tempo_name": "Prestissimo",
            "tempo_category": "Extremely Fast",
            "description": "가능한 한 아주 빠르게"
        }


def estimate_genre(
        bpm,
        energy_score,
        spectral_centroid=None,
        zero_crossing_rate=None,
        spectral_flatness=None,
        danceability=None
    ):
    scores = {
        "Ballad / Acoustic-like": 0,
        "Pop-like": 0,
        "Dance / EDM-like": 0,
        "Rock / Electronic-like": 0,
        "Jazz / Acoustic-like": 0,
        "Mixed / Unknown": 0
    }

    # Dance / EDM
    if bpm >= 120:
        scores["Dance / EDM-like"] += 2
    if energy_score >= 70:
        scores["Dance / EDM-like"] += 2
    if danceability is not None and danceability >= 55:
        scores["Dance / EDM-like"] += 1
    if spectral_flatness is not None and spectral_flatness >= 0.03:
        scores["Dance / EDM-like"] += 1

    # Pop
    if 90 <= bpm <= 130:
        scores["Pop-like"] += 2
    if 45 <= energy_score <= 75:
        scores["Pop-like"] += 2
    if danceability is not None and 35 <= danceability <= 65:
        scores["Pop-like"] += 1

    # Ballad / Acoustic
    if bpm < 95:
        scores["Ballad / Acoustic-like"] += 2
    if energy_score < 60:
        scores["Ballad / Acoustic-like"] += 2
    if spectral_centroid is not None and spectral_centroid < 2200:
        scores["Ballad / Acoustic-like"] += 1
    if zero_crossing_rate is not None and zero_crossing_rate < 0.05:
        scores["Ballad / Acoustic-like"] += 1

    # Rock / Electronic
    if bpm >= 130:
        scores["Rock / Electronic-like"] += 1
    if energy_score >= 65:
        scores["Rock / Electronic-like"] += 1
    if spectral_centroid is not None and spectral_centroid >= 2500:
        scores["Rock / Electronic-like"] += 1
    if zero_crossing_rate is not None and zero_crossing_rate >= 0.08:
        scores["Rock / Electronic-like"] += 1

    # Jazz / Acoustic
    if spectral_centroid is not None and spectral_centroid < 1800:
        scores["Jazz / Acoustic-like"] += 1
    if energy_score < 65:
        scores["Jazz / Acoustic-like"] += 1

    best_genre = max(scores, key=scores.get)

    if scores[best_genre] == 0:
        return "Mixed / Unknown"

    return best_genre


def estimate_rhythm_pattern(tempo, beats, onset_env, sr):
    if beats is None or len(beats) < 3:
        return "Rhythm not clearly detected"

    beat_times = librosa.frames_to_time(beats, sr=sr)
    beat_intervals = np.diff(beat_times)

    if len(beat_intervals) == 0:
        return "Rhythm not clearly detected"

    interval_mean = float(np.mean(beat_intervals))
    interval_std = float(np.std(beat_intervals))
    beat_variation = interval_std / (interval_mean + 1e-8)

    beat_strength = float(np.mean(onset_env))

    if beat_variation < 0.08 and beat_strength >= 1.5:
        return "Strong and steady beat"

    elif beat_variation < 0.12:
        return "Steady rhythm"

    elif beat_variation < 0.2:
        return "Moderate rhythmic variation"

    else:
        return "Irregular or expressive rhythm"


def estimate_mood(
        music_key,
        tempo,
        energy_score,
        spectral_centroid,
        danceability
    ):
    key_lower = music_key.lower() if music_key else ""

    is_minor = "minor" in key_lower
    is_major = "major" in key_lower

    if is_minor and energy_score < 55 and tempo <= 115:
        return "Melancholic / Emotional"

    elif is_major and energy_score >= 65 and tempo >= 110:
        return "Bright / Energetic"

    elif energy_score >= 75 and spectral_centroid >= 2500:
        return "Powerful / Intense"

    elif energy_score < 45 and tempo < 90:
        return "Calm / Soft"

    elif is_minor and energy_score >= 60:
        return "Dramatic / Emotional"

    elif danceability >= 60 and energy_score >= 60:
        return "Groovy / Uplifting"

    else:
        return "Neutral / Balanced"


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
        "lowest_pitch_hz": round(float(librosa.midi_to_hz(lowest_midi)), 2),
        "lowest_note": librosa.midi_to_note(lowest_midi),
        "highest_pitch_hz": round(float(librosa.midi_to_hz(highest_midi)), 2),
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


def detect_background_instruments_ast(
        background_file,
        processor,
        model,
        threshold=0.008,
        top_n=10
    ):
    audio, sr = librosa.load(background_file, sr=16000, mono=True)

    inputs = processor(
        audio,
        sampling_rate=16000,
        return_tensors="pt"
    )

    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits[0]
    scores = torch.sigmoid(logits)

    id2label = model.config.id2label

    instrument_groups = {
        "Drums / Percussion": [
            "drum", "drum kit", "snare drum", "bass drum",
            "cymbal", "percussion", "wood block", "cowbell",
            "hi-hat", "tabla", "bongo", "conga"
        ],
        "Electronic Instruments": [
            "synthesizer", "drum machine", "sampler", "keyboard"
        ],
        "Piano / Keyboard": [
            "piano", "electric piano", "keyboard"
        ],
        "Guitar": [
            "guitar", "electric guitar", "acoustic guitar"
        ],
        "Bass": [
            "bass guitar", "double bass", "electric bass"
        ],
        "Strings": [
            "violin", "viola", "cello", "string", "harp"
        ],
        "Brass": [
            "trumpet", "trombone", "brass", "horn"
        ],
        "Woodwinds": [
            "flute", "clarinet", "saxophone", "oboe"
        ],
        "Organ / Accordion": [
            "organ", "accordion"
        ]
    }

    detected_groups = {}
    top_scores, top_indices = torch.topk(scores, 30)

    for score, idx in zip(top_scores, top_indices):
        label = id2label[int(idx)]
        score_value = float(score)

        label_lower = label.lower()

        for group_name, keywords in instrument_groups.items():
            if any(keyword in label_lower for keyword in keywords):
                if group_name not in detected_groups:
                    detected_groups[group_name] = {
                        "instrument": group_name,
                        "score": score_value,
                        "percentage": round(score_value * 100, 1),
                        "matched_labels": [label]
                    }
                else:
                    if score_value > detected_groups[group_name]["score"]:
                        detected_groups[group_name]["score"] = score_value
                        detected_groups[group_name]["percentage"] = round(
                            score_value * 100,
                            1
                        )

                    detected_groups[group_name]["matched_labels"].append(label)

    detected = [
        info for info in detected_groups.values()
        if info["score"] >= threshold
    ]

    detected = sorted(
        detected,
        key=lambda x: x["score"],
        reverse=True
    )

    detected = detected[:top_n]

    return {
        "instrument_count": len(detected),
        "instruments": detected
    }


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
        job_id=None
    ):
    music_name = Path(audio_file).stem

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

    update_step(10, f"{file_index}번째 음악 오디오 원곡 분석 중")

    start = time.perf_counter()
    original_info = analyze_original_audio_librosa(audio_file, sample_rate)
    original_time = time.perf_counter() - start

    check_cancelled(job_id)

    update_step(25, f"{file_index}번째 음악 오디오 원곡 분석 완료")

    print(f"Duration: {original_info['duration']} sec")
    print(f"Duration (min:sec): {original_info['duration_text']}")
    print(f"Key: {original_info['key']}")
    print(f"Key Confidence: {original_info['key_confidence']}")

    tempo = original_info["tempo"]
    tempo_info = get_tempo_info(tempo)

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

    update_step(35, f"{file_index}번째 음악 오디오 보컬/배경음악 분리 중")

    def demucs_progress_callback(demucs_percent):
        mapped_percent = 35 + int((demucs_percent / 100) * 20)
        mapped_percent = max(35, min(55, mapped_percent))

        update_step(
            mapped_percent,
            f"{file_index}번째 음악 오디오 보컬/배경음악 분리 중 ({demucs_percent}%)"
        )

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

    update_step(55, f"{file_index}번째 음악 오디오 보컬/배경음악 분리 완료")

    update_step(65, f"{file_index}번째 음악 오디오 보컬 피치 분석 중")

    start = time.perf_counter()
    pitch_range = analyze_pitch_torchcrepe(vocal_file)
    pitch_time = time.perf_counter() - start

    check_cancelled(job_id)

    update_step(75, f"{file_index}번째 음악 오디오 보컬 피치 분석 완료")

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

    update_step(85, f"{file_index}번째 음악 오디오 배경 악기 분석 중")

    start = time.perf_counter()
    instrument_result = detect_background_instruments_ast(
        background_file,
        ast_processor,
        ast_model,
        threshold=0.008,
        top_n=10
    )
    instrument_time = time.perf_counter() - start

    check_cancelled(job_id)

    update_step(95, f"{file_index}번째 음악 오디오 결과 저장 중")

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
            "original_audio_analysis_time": round(original_time, 2),
            "vocal_separation_time": round(separation_time, 2),
            "vocal_pitch_analysis_time": round(pitch_time, 2),
            "background_instrument_analysis_time": round(instrument_time, 2),
            "total_analysis_time": round(total_time, 2)
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

    update_step(100, f"{file_index}번째 음악 오디오 분석 완료")

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


def run_uploaded_analysis(audio_file_paths, sample_rate=44100, job_id=None):
    if isinstance(audio_file_paths, str):
        audio_files = [audio_file_paths]
    else:
        audio_files = audio_file_paths

    print("분석할 파일 개수:", len(audio_files))
    print("분석할 파일 목록:", audio_files)

    return music_audio_analysis(
        audio_files,
        sample_rate,
        job_id=job_id
    )


def music_audio_analysis(audio_files, sample_rate=44100, job_id=None):
    all_results = []
    failed_indexes = set()

    program_start = time.perf_counter()

    ast_processor, ast_model = get_ast_model()

    total_files = len(audio_files)
    processed_count = 0

    init_progress(job_id, audio_files)
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
                job_id=job_id
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
            "text": f"{music_minutes} min {music_seconds} sec"
        },

        "total_program_execution_time": {
            "seconds": round(program_total_time, 2),
            "text": f"{minutes} min {seconds} sec"
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
        "current_step": "전체 분석 완료",
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
