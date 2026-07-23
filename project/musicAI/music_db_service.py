"""Database operations for MusicAI analysis results."""

import json

from sqlalchemy import func, text

from project import db
from project.models import AnalysisJob, MusicAudioFeature, MusicTrack


# =============================
# ID generation
# =============================

def get_next_id(sequence_name, prefix):
    """Generates the next ID using the database procedure."""
    db.session.execute(
        text("CALL sp_next_id(:sequence_name, :prefix, @new_id)"),
        {"sequence_name": sequence_name, "prefix": prefix},
    )

    new_id = db.session.execute(text("SELECT @new_id")).scalar()

    if new_id is None:
        raise RuntimeError(f"Failed to generate an ID for sequence: {sequence_name}")

    return new_id


# =============================
# Value conversion
# =============================

def to_float_or_none(value):
    """Converts a value to float or returns None."""
    if value is None: return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def json_serializer(value):
    """Converts NumPy-style values into JSON-compatible values."""
    if hasattr(value, "item"): return value.item()
    if hasattr(value, "tolist"): return value.tolist()
    return str(value)


def to_json_text(value):
    """Serialises a value as JSON text."""
    return json.dumps(value if value is not None else [], ensure_ascii=False, default=json_serializer)


def build_pitch_range(vocal_analysis):
    """Builds a vocal pitch-range description."""
    if not vocal_analysis: return None

    semitones = vocal_analysis.get("pitch_range_semitones")
    octaves = vocal_analysis.get("pitch_range_octaves")
    parts = []

    if semitones is not None: parts.append(f"{semitones} semitones")
    if octaves is not None: parts.append(f"{octaves} octaves")

    return " / ".join(parts) if parts else None


# =============================
# Analysis job management
# =============================

def create_analysis_job():
    """Creates a new analysis job."""
    request_job_id = get_next_id("analysis_job", "job")

    job = AnalysisJob(
        request_job_id=request_job_id,
        track_id=None,
        status="running",
        started_at=func.now(),
        is_active=1,
    )

    db.session.add(job)
    db.session.commit()

    return request_job_id


def mark_analysis_job_success(request_job_id, track_id):
    """Marks an analysis job as successful."""
    job = AnalysisJob.query.filter_by(request_job_id=request_job_id).first()

    if job is None: return False

    job.status = "success"
    job.track_id = track_id
    job.error_message = None
    job.finished_at = func.now()

    db.session.commit()
    return True


def mark_analysis_job_failed(request_job_id, error_message):
    """Marks an analysis job as failed."""
    job = AnalysisJob.query.filter_by(request_job_id=request_job_id).first()

    if job is None: return False

    job.status = "failed"
    job.error_message = str(error_message)
    job.finished_at = func.now()

    db.session.commit()
    return True


# =============================
# Music analysis result storage
# =============================

def save_music_analysis_to_db(result):
    """Saves a MusicAI analysis result to the database."""
    file_info = result.get("file_info") or {}
    original = result.get("original_audio_analysis") or {}
    vocal = result.get("vocal_pitch_analysis") or {}
    background = result.get("background_instrument_analysis") or {}

    try:
        track_id = get_next_id("music_track", "track")
        audio_feature_id = get_next_id("audio_feature", "af")

        track = MusicTrack(
            track_id=track_id,
            file_name=file_info.get("file_name"),
            file_path=file_info.get("file_path"),
            duration=to_float_or_none(file_info.get("duration")),
            is_active=1,
        )

        db.session.add(track)
        db.session.flush()

        instruments = background.get("instruments") or []
        instrument_types = to_json_text(instruments)
        pitch_range = build_pitch_range(vocal)

        audio_feature = MusicAudioFeature(
            audio_feature_id = audio_feature_id,
            track_id = track_id,

            music_key = original.get("key"),
            tempo = to_float_or_none(original.get("tempo")),
            rhythm_patterns = original.get("rhythm_pattern"),
            pitch_class_profiles = original.get("key_method"),

            min_pitch = vocal.get("lowest_note"),
            max_pitch = vocal.get("highest_note"),
            pitch_range = pitch_range,

            genre = original.get("genre"),
            instrument_types = instrument_types,
            energy = to_float_or_none(original.get("energy_score")),
            danceability = to_float_or_none(original.get("danceability_value")),
            mood = original.get("mood"),

            spectral_centroid = to_float_or_none(original.get("spectral_centroid_value")),
            spectral_flux = to_float_or_none(original.get("spectral_flux_value")),
            dynamic_range = to_float_or_none(original.get("dynamic_range_value")),
            harmonic_to_noise_ratio = to_float_or_none(original.get("harmonic_to_noise_ratio_value")),
            zero_crossing_rate = to_float_or_none(original.get("zero_crossing_rate_value")),
            spectral_bandwidth = to_float_or_none(original.get("spectral_bandwidth")),
            spectral_rolloff = to_float_or_none(original.get("spectral_rolloff")),
            spectral_flatness = to_float_or_none(original.get("spectral_flatness_value")),

            mfcc_mean = to_json_text(original.get("mfcc_mean")),
            mfcc_std = to_json_text(original.get("mfcc_std")),
            spectral_contrast_mean = to_json_text(original.get("spectral_contrast_mean")),
            chroma_mean = to_json_text(original.get("chroma_mean")),
            tonnetz_mean = to_json_text(original.get("tonnetz_mean")),

            created_at = func.now(),
            is_active = 1,
        )

        db.session.add(audio_feature)
        db.session.commit()

        return track_id

    except Exception:
        db.session.rollback()
        raise