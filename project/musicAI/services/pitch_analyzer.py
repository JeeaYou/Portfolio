"""Vocal pitch analysis using TorchCrepe."""

import librosa
import numpy as np
import torch
import torchcrepe


# =============================
# Pitch analysis settings
# =============================

# Audio sample rate required for pitch analysis
SAMPLE_RATE = 16000

# Number of audio samples between consecutive pitch predictions
HOP_LENGTH = 640

# Minimum periodicity required for a pitch value to be considered reliable
PERIODICITY_THRESHOLD = 0.7

# Supported vocal pitch range
MIN_NOTE = "A2"
MAX_NOTE = "C6"


# =============================
# Vocal pitch analysis
# =============================

def analyze_pitch_torchcrepe(vocal_file):
    """Analyses the vocal pitch range using TorchCrepe."""
    audio, _ = librosa.load(
        vocal_file,
        sr=SAMPLE_RATE,
        mono=True,
    )

    # Convert the NumPy audio array to a Torch tensor with a batch dimension.
    audio_tensor = torch.tensor(
        audio,
        dtype=torch.float32,
    ).unsqueeze(0)

    print("TorchCrepe pitch analysis started.")

    # Predict pitch frequency and periodicity for each audio frame.
    pitch, periodicity = torchcrepe.predict(
        audio_tensor,
        SAMPLE_RATE,
        HOP_LENGTH,
        fmin=librosa.note_to_hz(MIN_NOTE),
        fmax=librosa.note_to_hz(MAX_NOTE),
        model="tiny",
        batch_size=2048,
        device="cpu",
        return_periodicity=True,
    )

    print("TorchCrepe pitch analysis completed.")

    # Convert the prediction tensors to one-dimensional NumPy arrays.
    pitch = pitch.squeeze().cpu().numpy()
    periodicity = periodicity.squeeze().cpu().numpy()

    # Keep only reliable and positive pitch predictions.
    valid_pitch = pitch[
        (pitch > 0)
        & (periodicity > PERIODICITY_THRESHOLD)
    ]

    if valid_pitch.size == 0:
        return None

    # Convert pitch frequencies to MIDI note numbers.
    midi_notes = np.round(
        librosa.hz_to_midi(valid_pitch)
    ).astype(int)

    # Use percentiles to reduce the effect of pitch-detection outliers.
    lowest_midi = int(np.percentile(midi_notes, 10))
    highest_midi = int(np.percentile(midi_notes, 98))
    semitones = highest_midi - lowest_midi

    return {
        "lowest_pitch_hz": round(librosa.midi_to_hz(lowest_midi)),
        "lowest_note": librosa.midi_to_note(lowest_midi),
        "highest_pitch_hz": round(librosa.midi_to_hz(highest_midi)),
        "highest_note": librosa.midi_to_note(highest_midi),
        "pitch_range_semitones": semitones,
        "pitch_range_octaves": round(semitones / 12, 2),
    }