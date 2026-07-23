"""Flask routes for the MusicAI audio analysis service."""

import threading
import time
import traceback
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    render_template,
    request,
)
from werkzeug.utils import secure_filename

from .music_db_service import (
    create_analysis_job,
    mark_analysis_job_failed,
)
from .services.music_analysis_service import run_uploaded_analysis
from .services.progress_service import (
    AnalysisCancelled,
    init_progress,
    read_progress,
    request_cancel_analysis,
    write_progress,
)
from .utils.file_utils import format_display_file_name

# =============================
# Blueprint configuration
# =============================

bp = Blueprint(
    "musicAI",
    __name__,
    url_prefix="/musicAI",
    template_folder="templates",
    static_folder="static",
)

SUPPORTED_LANGUAGES = {"ko", "en", "zh"}
ALLOWED_EXTENSIONS = {"mp3", "wav"}
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"


# =============================
# Custom exceptions
# =============================

class UploadValidationError(ValueError):
    """Raised when uploaded audio files are missing or invalid."""

    pass


# =============================
# Language handling
# =============================

def get_lang():
    """Returns the current supported language code."""
    lang = getattr(g, "lang", None) or request.args.get("lang", "ko")
    return lang if lang in SUPPORTED_LANGUAGES else "ko"


# =============================
# Blueprint registration
# =============================

def register_into(app):
    """Registers the MusicAI blueprint with the Flask application."""
    app.register_blueprint(bp)


# =============================
# Upload helpers
# =============================

def allowed_file(filename):
    """Returns whether the uploaded file has a supported extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_uploaded_audio_files(files):
    """Validates and saves uploaded audio files."""
    valid_files = [
        file
        for file in files
        if file and file.filename
    ]

    if not valid_files:
        raise UploadValidationError("No audio files were uploaded.")

    for file in valid_files:
        if not allowed_file(file.filename):
            raise UploadValidationError(
                f"Unsupported file format: {file.filename}"
            )

    # Store each request in a separate directory to prevent filename conflicts.
    request_upload_dir = UPLOAD_DIR / str(time.time_ns())
    request_upload_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []

    for index, file in enumerate(valid_files, start=1):
        original_path = Path(file.filename)
        suffix = original_path.suffix.lower()
        safe_stem = secure_filename(original_path.stem) or "uploaded_audio"
        filename = f"{index:02d}_{safe_stem}{suffix}"
        save_path = request_upload_dir / filename

        file.save(save_path)
        saved_paths.append(str(save_path))

    return saved_paths


def create_failed_file_progress(saved_paths):
    """Creates failed progress entries for uploaded files."""
    return [
        {
            "index": index,
            "file_name": format_display_file_name(path),
            "status": "failed",
            "percent": 100,
        }
        for index, path in enumerate(saved_paths, start=1)
    ]


# =============================
# MusicAI page
# =============================

@bp.get("/", endpoint="index")
def index():
    """Renders the main MusicAI page."""
    return render_template(
        "musicAI.html",
        lang=get_lang(),
    )


# =============================
# Asynchronous analysis
# =============================

@bp.post("/analyze/start", endpoint="start_analysis")
def start_analysis():
    """
    Starts audio analysis in a background thread and immediately
    returns a job ID to the client.
    """
    try:
        lang = get_lang()
        files = request.files.getlist("audio_files")
        saved_paths = save_uploaded_audio_files(files)
        job_id = create_analysis_job()

        # Write the initial state before the background thread starts.
        init_progress(job_id, saved_paths, lang=lang)

        # Capture the actual Flask application for use inside the thread.
        flask_app = current_app._get_current_object()

        def background_analysis():
            """Runs audio analysis inside a Flask application context."""
            with flask_app.app_context():
                try:
                    result = run_uploaded_analysis(
                        saved_paths,
                        sample_rate=44100,
                        job_id=job_id,
                        lang=lang,
                    )

                    # A cancelled job is already handled by the analysis service.
                    if isinstance(result, dict) and result.get("cancelled"):
                        print("\n" + "=" * 100)
                        print("Background analysis cancelled.")
                        print(f"Job ID: {job_id}")
                        print("=" * 100)
                        return

                except AnalysisCancelled:
                    # Do not overwrite a cancelled job with an error state.
                    print("\n" + "=" * 100)
                    print("Background analysis cancelled.")
                    print(f"Job ID: {job_id}")
                    print("=" * 100)

                except Exception as error:
                    mark_analysis_job_failed(job_id, str(error))

                    print("\n" + "!" * 100)
                    print("Background analysis error")
                    print(traceback.format_exc())
                    print("!" * 100)

                    write_progress(job_id, {
                        "status": "error",
                        "total_files": len(saved_paths),
                        "current_file_index": 0,
                        "processed_count": 0,
                        "current_step": "An error occurred during analysis.",
                        "files": create_failed_file_progress(saved_paths),
                        "result": None,
                        "error": str(error),
                        "cancel_requested": False,
                        "cancel_reason": None,
                        "language": lang,
                    })

        analysis_thread = threading.Thread(target=background_analysis, daemon=True,)
        analysis_thread.start()

        return jsonify({
            "ok": True,
            "job_id": job_id,
        })

    except UploadValidationError as error:
        return jsonify({
            "ok": False,
            "error": str(error),
        }), 400

    except Exception as error:
        print("\n" + "!" * 100)
        print("Start analysis error")
        print(traceback.format_exc())
        print("!" * 100)

        return jsonify({
            "ok": False,
            "error": str(error),
        }), 500


# =============================
# Analysis cancellation
# =============================

@bp.post("/analysis/<job_id>/cancel", endpoint="cancel_analysis")
def cancel_analysis(job_id):
    """
    Cancels an analysis job and terminates its active Demucs process.

    This endpoint may be called when the user navigates away,
    refreshes the page, closes the page, or selects Home.
    """
    try:
        payload = request.get_json(silent=True) or {}
        reason = payload.get("reason") or "user_navigation"
        cancelled = request_cancel_analysis(job_id, reason=reason,)

        if not cancelled:
            return jsonify({
                "ok": False,
                "error": "The analysis job could not be found.",
            }), 404

        return jsonify({
            "ok": True,
            "status": "cancelled",
            "job_id": job_id,
        })

    except Exception as error:
        print("\n" + "!" * 100)
        print("Cancel analysis error")
        print(traceback.format_exc())
        print("!" * 100)

        return jsonify({
            "ok": False,
            "error": str(error),
        }), 500


# =============================
# Analysis progress
# =============================

@bp.get("/analyze/progress/<job_id>", endpoint="get_analysis_progress")
def get_analysis_progress(job_id):
    """Returns the current progress of an analysis job."""
    progress = read_progress(job_id)

    if progress is None:
        return jsonify({
            "ok": False,
            "error": "Analysis progress could not be found.",
        }), 404

    return jsonify({
        "ok": True,
        "progress": progress,
    })


# =============================
# Synchronous analysis
# =============================

@bp.post("/analyze", endpoint="analyze")
def analyze_music():
    """
    Runs audio analysis synchronously.

    The frontend currently uses /analyze/start, but this endpoint
    remains available for testing.
    """
    try:
        lang = get_lang()
        files = request.files.getlist("audio_files")
        saved_paths = save_uploaded_audio_files(files)

        result = run_uploaded_analysis(
            saved_paths,
            sample_rate=44100,
            lang=lang,
        )

        return jsonify({
            "ok": True,
            "result": result,
        })

    except UploadValidationError as error:
        return jsonify({
            "ok": False,
            "error": str(error),
        }), 400

    except Exception as error:
        print("\n" + "!" * 100)
        print("Analyse music error")
        print(traceback.format_exc())
        print("!" * 100)

        return jsonify({
            "ok": False,
            "error": str(error),
        }), 500