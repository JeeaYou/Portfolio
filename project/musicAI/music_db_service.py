import json

from sqlalchemy import text, func

from project import db
from project.models import (
    MusicTrack,
    MusicAudioFeature,
    AnalysisJob
)


def get_next_id(sequence_name, prefix):
    db.session.execute(
        text("CALL sp_next_id(:sequence_name, :prefix, @new_id)"),
        {
            "sequence_name": sequence_name,
            "prefix": prefix
        }
    )

    new_id = db.session.execute(
        text("SELECT @new_id")
    ).scalar()

    return new_id


def to_float_or_none(value):
    if value is None:
        return None

    try:
        return float(value)
    except Exception:
        return None


def to_json_text(value):
    if value is None:
        value = []

    return json.dumps(
        value,
        ensure_ascii=False,
        default=lambda x: float(x) if hasattr(x, "item") else str(x)
    )


def create_analysis_job():
    request_job_id = get_next_id("analysis_job", "job")

    job = AnalysisJob(
        request_job_id=request_job_id,
        track_id=None,
        status="running",
        started_at=func.now(),
        is_active=1
    )

    db.session.add(job)
    db.session.commit()

    return request_job_id


def mark_analysis_job_success(request_job_id, track_id):
    job = AnalysisJob.query.filter_by(
        request_job_id=request_job_id
    ).first()

    if not job:
        return

    job.status = "success"
    job.track_id = track_id
    job.error_message = None
    job.finished_at = func.now()

    db.session.commit()


def mark_analysis_job_failed(request_job_id, error_message):
    job = AnalysisJob.query.filter_by(
        request_job_id=request_job_id
    ).first()

    if not job:
        return

    job.status = "failed"
    job.error_message = str(error_message)
    job.finished_at = func.now()

    db.session.commit()


def save_music_analysis_to_db(result):
    file_info = result.get("file_info", {})
    original = result.get("original_audio_analysis", {})
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
            is_active=1
        )

        db.session.add(track)
        db.session.flush()

        instruments = background.get("instruments", [])
        instrument_types = to_json_text(instruments)

        min_pitch = vocal.get("lowest_note")
        max_pitch = vocal.get("highest_note")

        pitch_range = None
        if vocal:
            pitch_range = (
                f'{vocal.get("pitch_range_semitones")} semitones / '
                f'{vocal.get("pitch_range_octaves")} octaves'
            )

        audio_feature = MusicAudioFeature(
            audio_feature_id=audio_feature_id,
            track_id=track_id,

            music_key=original.get("key"),
            tempo=to_float_or_none(original.get("tempo")),

            rhythm_patterns=original.get("rhythm_pattern"),
            pitch_class_profiles=original.get("key_method"),

            min_pitch=min_pitch,
            max_pitch=max_pitch,
            pitch_range=pitch_range,

            genre=original.get("genre"),
            instrument_types=instrument_types,

            energy=to_float_or_none(original.get("energy_score")),
            danceability=to_float_or_none(original.get("danceability")),
            mood=original.get("mood"),

            spectral_centroid=to_float_or_none(original.get("spectral_centroid")),
            spectral_flux=to_float_or_none(original.get("spectral_flux")),
            dynamic_range=to_float_or_none(original.get("dynamic_range")),
            harmonic_to_noise_ratio=to_float_or_none(
                original.get("harmonic_to_noise_ratio")
            ),

            zero_crossing_rate=to_float_or_none(
                original.get("zero_crossing_rate")
            ),
            spectral_bandwidth=to_float_or_none(
                original.get("spectral_bandwidth")
            ),
            spectral_rolloff=to_float_or_none(
                original.get("spectral_rolloff")
            ),
            spectral_flatness=to_float_or_none(
                original.get("spectral_flatness")
            ),

            mfcc_mean=to_json_text(original.get("mfcc_mean")),
            mfcc_std=to_json_text(original.get("mfcc_std")),
            spectral_contrast_mean=to_json_text(
                original.get("spectral_contrast_mean")
            ),
            chroma_mean=to_json_text(original.get("chroma_mean")),
            tonnetz_mean=to_json_text(original.get("tonnetz_mean")),

            created_at=func.now(),
            is_active=1
        )

        db.session.add(audio_feature)
        db.session.commit()

        return track_id

    except Exception:
        db.session.rollback()
        raise