from flask import Blueprint, render_template, jsonify, request, current_app
from werkzeug.utils import secure_filename
from pathlib import Path
import time
import threading
import traceback


bp = Blueprint(
    "musicAI",
    __name__,
    url_prefix="/musicAI",
    template_folder="templates",
    static_folder="static"
)

ALLOWED_EXTENSIONS = {"mp3", "wav"}


def register_into(app):
    """
    project/__init__.py 에서 musicAI.register_into(app) 로 호출되므로
    반드시 필요한 함수입니다.
    """
    app.register_blueprint(bp)


@bp.get("/", endpoint="index")
def index():
    return render_template("musicAI.html")


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


@bp.post("/analyze/start", endpoint="start_analysis")
def start_analysis():
    """
    분석 시작 API.
    분석 결과를 기다리지 않고 job_id만 먼저 반환하고,
    실제 분석은 백그라운드 thread에서 실행한다.
    """
    try:
        files = request.files.getlist("audio_files")

        if not files:
            return jsonify({
                "ok": False,
                "error": "업로드된 음악 파일이 없습니다."
            }), 400

        upload_dir = Path(__file__).resolve().parent / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = []

        for file in files:
            if not file or file.filename == "":
                continue

            if not allowed_file(file.filename):
                return jsonify({
                    "ok": False,
                    "error": f"지원하지 않는 파일 형식입니다: {file.filename}"
                }), 400

            original_filename = Path(file.filename).name
            save_path = upload_dir / original_filename

            file.save(save_path)
            saved_paths.append(str(save_path))

        if not saved_paths:
            return jsonify({
                "ok": False,
                "error": "분석할 수 있는 음악 파일이 없습니다."
            }), 400

        from .music_db_service import create_analysis_job

        job_id = create_analysis_job()

        from .service_musicAI import (
            init_progress,
            run_uploaded_analysis,
            write_progress
        )

        init_progress(job_id, saved_paths)

        flask_app = current_app._get_current_object()

        def background_analysis():
            with flask_app.app_context():
                try:
                    result = run_uploaded_analysis(
                        saved_paths,
                        sample_rate=44100,
                        job_id=job_id
                    )

                    # 취소된 작업은 service_musicAI.py에서 cancelled로 처리함.
                    # 여기서 error로 다시 덮어쓰면 안 됨.
                    if isinstance(result, dict) and result.get("cancelled"):
                        print("\n" + "=" * 100)
                        print("Background Analysis Cancelled")
                        print(f"job_id: {job_id}")
                        print("=" * 100)
                        return

                except Exception as e:
                    from .music_db_service import mark_analysis_job_failed
                    mark_analysis_job_failed(job_id, str(e))

                    print("\n" + "!" * 100)
                    print("Background Analysis Error")
                    print(traceback.format_exc())
                    print("!" * 100)

                    write_progress(job_id, {
                        "status": "error",
                        "total_files": len(saved_paths),
                        "current_file_index": 0,
                        "processed_count": 0,
                        "current_step": "분석 중 오류가 발생했습니다.",
                        "files": [
                            {
                                "index": i + 1,
                                "file_name": Path(path).name,
                                "status": "failed",
                                "percent": 100
                            }
                            for i, path in enumerate(saved_paths)
                        ],
                        "result": None,
                        "error": str(e),
                        "cancel_requested": False,
                        "cancel_reason": None
                    })

        thread = threading.Thread(target=background_analysis, daemon=True)
        thread.start()

        return jsonify({
            "ok": True,
            "job_id": job_id
        })

    except Exception as e:
        print("\n" + "!" * 100)
        print("Start Analysis Error")
        print(traceback.format_exc())
        print("!" * 100)

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@bp.post("/analysis/<job_id>/cancel", endpoint="cancel_analysis")
def cancel_analysis(job_id):
    """
    분석 취소 API.

    프론트에서 Home 클릭, 페이지 이동, 새로고침, 닫기 등이 발생하면 호출된다.
    service_musicAI.py의 request_cancel_analysis()가
    progress JSON에 cancel_requested=True를 저장하고,
    실행 중인 Demucs subprocess가 있으면 terminate/kill 처리한다.
    """
    try:
        payload = request.get_json(silent=True) or {}
        reason = payload.get("reason") or "user_navigation"

        from .service_musicAI import request_cancel_analysis

        cancelled = request_cancel_analysis(job_id, reason=reason)

        if not cancelled:
            return jsonify({
                "ok": False,
                "error": "취소할 분석 작업을 찾을 수 없습니다."
            }), 404

        return jsonify({
            "ok": True,
            "status": "cancelled",
            "job_id": job_id
        })

    except Exception as e:
        print("\n" + "!" * 100)
        print("Cancel Analysis Error")
        print(traceback.format_exc())
        print("!" * 100)

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@bp.get("/analyze/progress/<job_id>", endpoint="get_analysis_progress")
def get_analysis_progress(job_id):
    """
    프론트에서 진행률 조회할 때 호출하는 API.
    """
    from .service_musicAI import read_progress

    progress = read_progress(job_id)

    if progress is None:
        return jsonify({
            "ok": False,
            "error": "분석 진행 정보를 찾을 수 없습니다."
        }), 404

    return jsonify({
        "ok": True,
        "progress": progress
    })


@bp.post("/analyze", endpoint="analyze")
def analyze_music():
    """
    기존 동기 분석 API.
    현재 프론트에서는 /analyze/start 를 사용하지만,
    테스트용으로 남겨둔다.
    """
    try:
        files = request.files.getlist("audio_files")

        if not files:
            return jsonify({
                "ok": False,
                "error": "업로드된 음악 파일이 없습니다."
            }), 400

        upload_dir = Path(__file__).resolve().parent / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = []

        for file in files:
            if not file or file.filename == "":
                continue

            if not allowed_file(file.filename):
                return jsonify({
                    "ok": False,
                    "error": f"지원하지 않는 파일 형식입니다: {file.filename}"
                }), 400

            suffix = Path(file.filename).suffix.lower()
            safe_stem = secure_filename(Path(file.filename).stem) or "uploaded_audio"

            filename = f"{int(time.time() * 1000)}_{safe_stem}{suffix}"

            save_path = upload_dir / filename
            file.save(save_path)

            saved_paths.append(str(save_path))

        if not saved_paths:
            return jsonify({
                "ok": False,
                "error": "분석할 수 있는 음악 파일이 없습니다."
            }), 400

        from .service_musicAI import run_uploaded_analysis

        result = run_uploaded_analysis(
            saved_paths,
            sample_rate=44100
        )

        return jsonify({
            "ok": True,
            "result": result
        })

    except Exception as e:
        print("\n" + "!" * 100)
        print("Analyze Music Error")
        print(traceback.format_exc())
        print("!" * 100)

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500