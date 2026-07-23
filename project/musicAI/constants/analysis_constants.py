import threading
from pathlib import Path

import numpy as np


# =============================
# Directory paths
# =============================

# musicAI project directory.
MUSIC_AI_DIR = Path(__file__).resolve().parents[1]

# Stores uploaded audio files.
UPLOAD_DIR = MUSIC_AI_DIR / "static" /  "music" /  "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Stores analysis progress JSON files.
PROGRESS_DIR = MUSIC_AI_DIR / "static" /  "music" /  "progress"
PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

# Stores audio files separated by Demucs.
SEPARATED_DIR = MUSIC_AI_DIR / "static" /  "music" /  "separated"
SEPARATED_DIR.mkdir(parents=True, exist_ok=True)

# Stores final audio analysis result files.
ANALYSIS_RESULTS_DIR = MUSIC_AI_DIR / "static" /  "music" /  "analysis_results"
ANALYSIS_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# =============================
# Active Demucs processes
# =============================

# Stores active Demucs processes by job ID
_CURRENT_DEMUCS_PROCESSES = {}

# Protects access to the active process dictionary
_CURRENT_DEMUCS_PROCESSES_LOCK = threading.Lock()


# =============================
# Musical key profiles
# =============================

# Chromatic note names ordered by pitch class
NOTE_NAMES = [
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B",
]

# Krumhansl–Schmuckler major key profile
MAJOR_PROFILE = np.array([
    6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
    2.52, 5.19, 2.39, 3.66, 2.29, 2.88,
])

# Krumhansl–Schmuckler minor key profile
MINOR_PROFILE = np.array([
    6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
    2.54, 4.75, 3.98, 2.69, 3.34, 3.17,
])