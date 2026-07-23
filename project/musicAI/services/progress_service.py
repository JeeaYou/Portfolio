"""Progress tracking and cancellation handling for MusicAI analysis."""

import json
from pathlib import Path

from ..constants.analysis_constants import (
    PROGRESS_DIR,
    _CURRENT_DEMUCS_PROCESSES,
    _CURRENT_DEMUCS_PROCESSES_LOCK,
)
from ..constants.analysis_messages import (
    CANCELLED_TEXT,
    PREPARING_TEXT,
)
from ..utils.process_utils import terminate_process_tree
from ..utils.file_utils import format_display_file_name

# =============================
# Analysis cancellation exception
# =============================

class AnalysisCancelled(Exception):
    """Raised when an audio analysis job is cancelled."""

    pass


# =============================
# Progress file handling
# =============================

def get_progress_path(job_id):
    """Returns the progress JSON path for the specified job."""
    return PROGRESS_DIR / f"{job_id}.json"


def write_progress(job_id, data):
    """Writes progress data to a JSON file atomically."""
    if not job_id:
        return

    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

    progress_path = get_progress_path(job_id)
    temp_path = progress_path.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    temp_path.replace(progress_path)


def read_progress(job_id):
    """Reads and returns progress data for the specified job."""
    if not job_id:
        return None

    progress_path = get_progress_path(job_id)

    if not progress_path.exists():
        return None

    try:
        with open(progress_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return None


# =============================
# File progress generation
# =============================

def make_progress_files(
    audio_files,
    current_index=0,
    current_percent=0,
    processed_count=0,
    failed_indexes=None,
):
    """Creates progress information for each audio file."""
    failed_indexes = failed_indexes or set()
    files = []

    for index, audio_file in enumerate(audio_files, start=1):
        if index in failed_indexes:
            status, percent = "failed", 100
        elif current_index and index == current_index:
            status, percent = "running", current_percent
        elif index <= processed_count:
            status, percent = "done", 100
        else:
            status, percent = "waiting", 0

        files.append({
            "index": index,
            "file_name": format_display_file_name(audio_file),
            "status": status,
            "percent": percent,
        })

    return files


def init_progress(job_id, audio_files, **kwargs):
    """Initialises progress data for a new analysis job."""
    lang = kwargs.get("lang", "ko")
    lang = lang if lang in PREPARING_TEXT else "ko"

    write_progress(job_id, {
        "status": "running",
        "total_files": len(audio_files),
        "current_file_index": 0,
        "processed_count": 0,
        "current_step": PREPARING_TEXT[lang],
        "files": make_progress_files(audio_files),
        "result": None,
        "error": None,
        "cancel_requested": False,
        "cancel_reason": None,
        "language": lang,
    })


# =============================
# Analysis cancellation handling
# =============================

def request_cancel_analysis(job_id, reason="user_navigation"):
    """
    Saves the cancellation state and terminates the active
    Demucs process associated with the job.
    """
    if not job_id:
        return False

    progress = read_progress(job_id)

    if progress is None:
        return False

    lang = progress.get("language", "ko")
    lang = lang if lang in CANCELLED_TEXT else "ko"

    progress.update({
        "status": "cancelled",
        "current_step": CANCELLED_TEXT[lang],
        "cancel_requested": True,
        "cancel_reason": reason,
        "error": None,
    })

    for file_item in progress.get("files") or []:
        if file_item.get("status") == "running":
            file_item["status"] = "failed"
            file_item["percent"] = 100

    write_progress(job_id, progress)

    with _CURRENT_DEMUCS_PROCESSES_LOCK:
        process = _CURRENT_DEMUCS_PROCESSES.get(job_id)

    if process and process.poll() is None:
        print()
        print("=" * 100)
        print(
            f"Analysis cancellation request received: "
            f"job_id={job_id}, reason={reason}"
        )
        print("Terminating the active Demucs process.")
        print("=" * 100)

        terminate_process_tree(process)

    return True


def is_cancel_requested(job_id):
    """Returns whether cancellation has been requested for the job."""
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
    """Raises AnalysisCancelled when cancellation has been requested."""
    if is_cancel_requested(job_id):
        raise AnalysisCancelled("Analysis was cancelled.")


def write_cancelled_progress(
    job_id,
    audio_files=None,
    current_index=0,
    processed_count=0,
    reason="user_navigation",
    lang=None,
):
    """Writes the final progress state for a cancelled analysis job."""
    if not job_id:
        return

    audio_files = audio_files or []

    # Reuse the language stored in the current progress data when
    # the caller does not explicitly provide one.
    if lang is None:
        current_progress = read_progress(job_id) or {}
        lang = current_progress.get("language", "ko")

    lang = lang if lang in CANCELLED_TEXT else "ko"
    files = []

    for index, audio_file in enumerate(audio_files, start=1):
        if index <= processed_count:
            status, percent = "done", 100
        elif current_index and index == current_index:
            status, percent = "failed", 100
        else:
            status, percent = "waiting", 0

        files.append({
            "index": index,
            "file_name": format_display_file_name(audio_file),
            "status": status,
            "percent": percent,
        })

    write_progress(job_id, {
        "status": "cancelled",
        "total_files": len(audio_files),
        "current_file_index": current_index,
        "processed_count": processed_count,
        "current_step": CANCELLED_TEXT[lang],
        "files": files,
        "result": None,
        "error": None,
        "cancel_requested": True,
        "cancel_reason": reason,
        "language": lang,
    })