"""Vocal separation service using Demucs."""

import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import certifi

from ..constants.analysis_constants import (
    SEPARATED_DIR,
    _CURRENT_DEMUCS_PROCESSES,
    _CURRENT_DEMUCS_PROCESSES_LOCK,
)
from ..utils.process_utils import terminate_process_tree
from .progress_service import (
    AnalysisCancelled,
    check_cancelled,
    is_cancel_requested,
)


# =============================
# Demucs progress display
# =============================

def extract_percent_from_text(text):
    """Extracts the last percentage value from a line of Demucs output."""
    matches = re.findall(r"(\d{1,3})\s*%", text)
    return max(0, min(100, int(matches[-1]))) if matches else None


def print_single_line_progress(label, percent):
    """Displays a single-line progress bar in the terminal."""
    bar_length = 30
    percent = max(0, min(100, int(percent)))
    filled_length = int(bar_length * percent / 100)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    print(f"\r{label} [{bar}] {percent:3d}%", end="\n", flush=True)


def unregister_demucs_process(job_id, process):
    """Removes a completed Demucs process from the active process registry."""
    if not job_id:
        return

    with _CURRENT_DEMUCS_PROCESSES_LOCK:
        if _CURRENT_DEMUCS_PROCESSES.get(job_id) is process:
            _CURRENT_DEMUCS_PROCESSES.pop(job_id, None)


# =============================
# Demucs execution
# =============================

def run_demucs_with_percent_bar(
    command,
    env,
    log_path,
    progress_callback=None,
    job_id=None,
):
    """
    Runs Demucs, saves its output to a log file, and displays
    a single-line progress bar in the terminal.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Shared progress state used by the main and output-reader threads.
    state = {"percent": 0, "last_rendered": -1}
    state_lock = threading.Lock()

    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write("\n" + "=" * 100 + "\n")
        log_file.write(f"Demucs started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write("Command:\n")
        log_file.write(" ".join(command) + "\n")
        log_file.write("=" * 100 + "\n")
        log_file.flush()

        # start_new_session allows the entire process group to be terminated.
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            start_new_session=True,
        )

        # Register the process so that it can be cancelled externally.
        if job_id:
            with _CURRENT_DEMUCS_PROCESSES_LOCK:
                _CURRENT_DEMUCS_PROCESSES[job_id] = process

        def read_demucs_output():
            """Reads Demucs output and extracts its reported progress."""
            for line in iter(process.stdout.readline, ""):
                log_file.write(line)
                log_file.flush()

                parsed_percent = extract_percent_from_text(line)

                if parsed_percent is not None:
                    with state_lock:
                        state["percent"] = max(
                            state["percent"],
                            min(parsed_percent, 99),
                        )

        reader_thread = threading.Thread(
            target=read_demucs_output,
            daemon=True,
        )
        reader_thread.start()

        fallback_percent = 0
        print_single_line_progress("Vocal separation", 0)

        try:
            while process.poll() is None:
                if is_cancel_requested(job_id):
                    print()
                    print("=" * 100)
                    print(f"Demucs cancellation detected: job_id={job_id}")
                    print("=" * 100)

                    terminate_process_tree(process)
                    raise AnalysisCancelled("Analysis was cancelled.")

                with state_lock:
                    real_percent = state["percent"]

                # Use estimated progress when Demucs does not report a percentage.
                if real_percent:
                    display_percent = real_percent
                else:
                    fallback_percent = min(fallback_percent + 1, 95)
                    display_percent = fallback_percent

                with state_lock:
                    should_render = display_percent != state["last_rendered"]
                    state["last_rendered"] = display_percent

                if should_render:
                    print_single_line_progress(
                        "Vocal separation",
                        display_percent,
                    )

                    if progress_callback:
                        progress_callback(display_percent)

                time.sleep(0.35)

        finally:
            reader_thread.join(timeout=2)
            unregister_demucs_process(job_id, process)

        if is_cancel_requested(job_id):
            raise AnalysisCancelled("Analysis was cancelled.")

        # Raise an error when Demucs exits unsuccessfully.
        if process.returncode != 0:
            print_single_line_progress("Vocal separation failed", 100)
            print()
            print(f"Check the Demucs error log: {log_path.resolve()}")

            raise subprocess.CalledProcessError(
                process.returncode,
                command,
            )

        print_single_line_progress("Vocal separation", 100)
        print()

        if progress_callback:
            progress_callback(100)


# =============================
# Vocal separation
# =============================

def separate_vocals(audio_file, progress_callback=None, job_id=None):
    """Separates vocals and background audio using Demucs."""
    audio_path = Path(audio_file)

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    check_cancelled(job_id)

    song_name = audio_path.stem
    output_dir = SEPARATED_DIR / "htdemucs" / song_name
    vocals_path = output_dir / "vocals.wav"
    no_vocals_path = output_dir / "no_vocals.wav"

    # Reuse existing separated files when both outputs are available.
    if vocals_path.exists() and no_vocals_path.exists():
        print_single_line_progress("Using cached vocal separation", 100)
        print()

        if progress_callback:
            progress_callback(100)

        check_cancelled(job_id)

        return {
            "vocals_path": str(vocals_path),
            "no_vocals_path": str(no_vocals_path),
        }

    command = [
        sys.executable,
        "-m",
        "demucs",
        "--two-stems=vocals",
        "-o",
        str(SEPARATED_DIR),
        str(audio_path),
    ]

    # Configure the certificate bundle used by Demucs and Requests.
    env = os.environ.copy()
    certificate_path = certifi.where()
    env["SSL_CERT_FILE"] = certificate_path
    env["REQUESTS_CA_BUNDLE"] = certificate_path

    log_path = (
        SEPARATED_DIR
        / "demucs_logs"
        / f"{song_name}_demucs.log"
    )

    run_demucs_with_percent_bar(
        command=command,
        env=env,
        log_path=log_path,
        progress_callback=progress_callback,
        job_id=job_id,
    )

    print("_" * 100)

    # Confirm that Demucs created both expected output files.
    if not vocals_path.exists():
        raise FileNotFoundError(
            f"Demucs vocal file not found: {vocals_path}"
        )

    if not no_vocals_path.exists():
        raise FileNotFoundError(
            f"Demucs background music file not found: {no_vocals_path}"
        )

    check_cancelled(job_id)

    return {
        "vocals_path": str(vocals_path),
        "no_vocals_path": str(no_vocals_path),
    }