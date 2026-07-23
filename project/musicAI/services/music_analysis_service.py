"""High-level orchestration for MusicAI audio analysis."""

import time
from pathlib import Path

from ..constants.analysis_constants import ANALYSIS_RESULTS_DIR
from ..constants.analysis_messages import UPDATE_STEP_TEXT
from ..music_db_service import (
    mark_analysis_job_failed,
    mark_analysis_job_success,
    save_music_analysis_to_db,
)
from ..utils.audio_utils import format_duration_text
from ..utils.file_utils import (
    format_display_file_name,
    save_json_result
)
from .instrument_analyzer import detect_background_instruments_ast, get_ast_model
from .original_audio_analyzer import analyze_original_audio_librosa, get_tempo_info
from .pitch_analyzer import analyze_pitch_torchcrepe
from .progress_service import (
    AnalysisCancelled,
    check_cancelled,
    init_progress,
    is_cancel_requested,
    make_progress_files,
    write_cancelled_progress,
    write_progress,
)
from .vocal_separator import separate_vocals


FILE_PROGRESS_TEXT = {
    "ko": {
        "start": "{index}번째 음악 오디오 분석 시작",
        "completed": "{index}번째 음악 오디오 분석 완료",
        "failed": "{index}번째 음악 오디오 분석 실패",
        "partial_failure": "일부 파일 분석 실패",
        "all_completed": "전체 분석 완료",
    },
    "en": {
        "start": "Starting analysis of audio file {index}",
        "completed": "Audio file {index} analysis completed",
        "failed": "Audio file {index} analysis failed",
        "partial_failure": "Some files failed to analyse",
        "all_completed": "Analysis completed",
    },
    "zh": {
        "start": "开始分析第 {index} 个音频文件",
        "completed": "第 {index} 个音频文件分析完成",
        "failed": "第 {index} 个音频文件分析失败",
        "partial_failure": "部分文件分析失败",
        "all_completed": "分析完成",
    },
}


def normalize_lang(lang):
    return lang if lang in UPDATE_STEP_TEXT else "ko"


def get_file_progress_text(index, status, lang):
    return FILE_PROGRESS_TEXT[normalize_lang(lang)][status].format(index=index)


# =============================
# Analyze one music file
# =============================

def analyze_one_music_file(
    audio_file,
    ast_processor,
    ast_model,
    sample_rate=44100,
    file_index=None,
    progress_callback=None,
    job_id=None,
    lang="ko",
):
    lang = normalize_lang(lang)
    step_text = UPDATE_STEP_TEXT[lang]
    music_name = Path(format_display_file_name(audio_file)).stem

    print("\n" + "=" * 100)
    print(f"{file_index}. {music_name}" if file_index is not None else music_name)
    print("=" * 100)

    total_start = time.perf_counter()
    check_cancelled(job_id)

    def update_step(percent, step):
        if progress_callback: progress_callback(percent, step)

    # =============================
    # Original audio analysis
    # =============================

    update_step(10, step_text["original_analyzing"])

    start = time.perf_counter()
    original_info = analyze_original_audio_librosa(audio_file, sample_rate, lang)
    original_time = time.perf_counter() - start

    check_cancelled(job_id)
    update_step(25, step_text["original_completed"])

    tempo = original_info["tempo"]
    tempo_info = get_tempo_info(tempo, lang)

    print(f"Duration: {original_info['duration']} sec")
    print(f"Duration (min:sec): {original_info['duration_text']}")
    print(f"Key: {original_info['key']}")
    print(f"Key Confidence: {original_info['key_confidence']}")
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

    # =============================
    # Vocal separation
    # =============================

    update_step(35, step_text["separating"])

    def demucs_progress_callback(demucs_percent):
        mapped_percent = max(35, min(55, 35 + int((demucs_percent / 100) * 20)))
        update_step(mapped_percent, f"{step_text['separating_percent']} ({demucs_percent}%)")

    start = time.perf_counter()
    separated_files = separate_vocals(
        audio_file,
        progress_callback=demucs_progress_callback,
        job_id=job_id,
    )
    separation_time = time.perf_counter() - start

    check_cancelled(job_id)

    vocal_file = separated_files["vocals_path"]
    background_file = separated_files["no_vocals_path"]

    update_step(55, step_text["separation_completed"])

    # =============================
    # Vocal pitch analysis
    # =============================

    update_step(65, step_text["pitch_analyzing"])

    start = time.perf_counter()
    pitch_range = analyze_pitch_torchcrepe(vocal_file)
    pitch_time = time.perf_counter() - start

    check_cancelled(job_id)
    update_step(75, step_text["pitch_completed"])

    if pitch_range:
        print(f"Lowest Vocal Pitch: {pitch_range['lowest_pitch_hz']} Hz")
        print(f"Lowest Vocal Note: {pitch_range['lowest_note']}")
        print(f"Highest Vocal Pitch: {pitch_range['highest_pitch_hz']} Hz")
        print(f"Highest Vocal Note: {pitch_range['highest_note']}")
        print(f"Vocal Pitch Range: {pitch_range['pitch_range_semitones']} semitones")
        print(f"Vocal Pitch Range Octaves: {pitch_range['pitch_range_octaves']} octaves")
    else:
        print("Vocal Pitch: No analysable vocal pitch was found.")

    print("-" * 100)

    # =============================
    # Background instrument analysis
    # =============================

    update_step(85, step_text["instrument_analyzing"])

    start = time.perf_counter()
    instrument_result = detect_background_instruments_ast(
        background_file,
        ast_processor,
        ast_model,
        threshold=0.008,
        top_n=10,
        lang=lang,
    )
    instrument_time = time.perf_counter() - start

    check_cancelled(job_id)
    update_step(95, step_text["saving"])

    print(f"Background Instrument Count: {instrument_result['instrument_count']}")
    print("Background Instruments:")
    print("-" * 100)

    for item in instrument_result["instruments"]:
        print(f"{item['instrument']}: {item['percentage']}% ({', '.join(item['matched_labels'])})")

    total_time = time.perf_counter() - total_start

    # =============================
    # Result data
    # =============================

    result = {
        "file_info": {
            "file_name": format_display_file_name(audio_file),
            "file_path": str(audio_file),
            "duration": round(original_info["duration"], 2),
            "duration_text": original_info["duration_text"],
        },
        "original_audio_analysis": {
            "key": original_info["key"],
            "key_confidence": f"{float(original_info['key_confidence']) * 100}%",
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
            "spectral_centroid_value": original_info["spectral_centroid_value"],
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
            "dynamic_range_value": original_info["dynamic_range_value"],
            "harmonic_to_noise_ratio": original_info["hnr"],
            "harmonic_to_noise_ratio_value": original_info["hnr_value"],
            "danceability": original_info["danceability"],
            "danceability_value": original_info["danceability_value"],
        },
        "vocal_pitch_analysis": pitch_range,
        "background_instrument_analysis": {
            "instrument_count": instrument_result["instrument_count"],
            "instruments": instrument_result["instruments"],
        },
        "analysis_time_summary": {
            "original_audio_analysis_time": round(original_time),
            "vocal_separation_time": round(separation_time),
            "vocal_pitch_analysis_time": round(pitch_time),
            "background_instrument_analysis_time": round(instrument_time),
            "total_analysis_time": round(total_time),
        },
    }

    # =============================
    # Save result
    # =============================

    result_dir = Path(vocal_file).parent
    json_path = result_dir / f"{Path(audio_file).stem}_analysis.json"

    check_cancelled(job_id)
    save_json_result(result, json_path)

    track_id = save_music_analysis_to_db(result)
    result["db_track_id"] = track_id

    if job_id: mark_analysis_job_success(job_id, track_id)

    update_step(100, step_text["analysis_completed"])

    print(f"Analysis result saved: {json_path.resolve()}")
    print(f"Analysis result saved to DB. track_id={track_id}")

    return result


# =============================
# Uploaded file analysis
# =============================

def run_uploaded_analysis(audio_file_paths, sample_rate=44100, job_id=None, lang="ko"):
    audio_files = [audio_file_paths] if isinstance(audio_file_paths, str) else list(audio_file_paths)
    lang = normalize_lang(lang)

    print(f"Number of files to analyse: {len(audio_files)}")
    print(f"Files to analyse: {audio_files}")

    return music_audio_analysis(audio_files, sample_rate, job_id=job_id, lang=lang)


# =============================
# Multiple music file analysis
# =============================

def music_audio_analysis(audio_files, sample_rate=44100, job_id=None, lang="ko"):
    lang = normalize_lang(lang)

    all_results = []
    failed_indexes = set()
    processed_count = 0
    total_files = len(audio_files)
    program_start = time.perf_counter()

    ast_processor, ast_model = get_ast_model()

    init_progress(job_id, audio_files, lang=lang)
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
                    failed_indexes=failed_indexes,
                ),
                "result": None,
                "error": None,
                "cancel_requested": False,
                "cancel_reason": None,
                "language": lang,
            })

        try:
            update_current_file(5, get_file_progress_text(index, "start", lang))

            result = analyze_one_music_file(
                audio_file,
                ast_processor,
                ast_model,
                sample_rate,
                file_index=index,
                progress_callback=update_current_file,
                job_id=job_id,
                lang=lang,
            )

            all_results.append(result)

        except AnalysisCancelled:
            was_cancelled = True

            write_cancelled_progress(
                job_id,
                audio_files=audio_files,
                current_index=index,
                processed_count=processed_count,
            )

            print("\n" + "=" * 100)
            print(f"Analysis was cancelled. job_id={job_id}")
            print("=" * 100)

            return {
                "cancelled": True,
                "job_id": job_id,
                "total_file_count": len(all_results),
                "results": all_results,
            }

        except Exception as error:
            failed_indexes.add(index)

            if job_id: mark_analysis_job_failed(job_id, str(error))

            print("\n" + "!" * 100)
            print(f"Analysis failed: {audio_file}")
            print(f"Error: {error}")
            print("!" * 100)

            write_progress(job_id, {
                "status": "running",
                "total_files": total_files,
                "current_file_index": index,
                "processed_count": processed_count,
                "current_step": get_file_progress_text(index, "failed", lang),
                "files": make_progress_files(
                    audio_files,
                    current_index=index,
                    current_percent=100,
                    processed_count=processed_count,
                    failed_indexes=failed_indexes,
                ),
                "result": None,
                "error": str(error),
                "cancel_requested": False,
                "cancel_reason": None,
                "language": lang,
            })

        finally:
            if was_cancelled: continue

            processed_count += 1
            current_status = "completed" if result is not None else "failed"

            write_progress(job_id, {
                "status": "running",
                "total_files": total_files,
                "current_file_index": 0,
                "processed_count": processed_count,
                "current_step": get_file_progress_text(index, current_status, lang),
                "files": make_progress_files(
                    audio_files,
                    processed_count=processed_count,
                    failed_indexes=failed_indexes,
                ),
                "result": None,
                "error": None if result is not None else FILE_PROGRESS_TEXT[lang]["partial_failure"],
                "cancel_requested": False,
                "cancel_reason": None,
                "language": lang,
            })

            print("\n" + "=" * 100)
            print("Progress Summary")
            print("-" * 100)
            print(f"Progress: {processed_count}/{total_files}")

            if result:
                time_info = result["analysis_time_summary"]
                print(f"Original Audio Analysis: {time_info['original_audio_analysis_time']} sec")
                print(f"Vocal Separation: {time_info['vocal_separation_time']} sec")
                print(f"Vocal Pitch Analysis: {time_info['vocal_pitch_analysis_time']} sec")
                print(f"Background Instrument Analysis: {time_info['background_instrument_analysis_time']} sec")
                print(f"Current File Total Analysis Time: {time_info['total_analysis_time']} sec")
            else:
                print("Analysis Time Summary: Unavailable because the analysis failed.")

    if is_cancel_requested(job_id):
        write_cancelled_progress(
            job_id,
            audio_files=audio_files,
            current_index=0,
            processed_count=processed_count,
        )

        return {
            "cancelled": True,
            "job_id": job_id,
            "total_file_count": len(all_results),
            "results": all_results,
        }

    total_music_duration = sum(result["file_info"]["duration"] for result in all_results)
    program_total_time = time.perf_counter() - program_start

    summary_result = {
        "total_file_count": len(all_results),
        "total_music_duration": {
            "seconds": round(total_music_duration, 2),
            "text": format_duration_text(total_music_duration, lang),
        },
        "total_program_execution_time": {
            "seconds": round(program_total_time, 2),
            "text": format_duration_text(program_total_time, lang),
        },
        "results": all_results,
    }

    summary_json_path = ANALYSIS_RESULTS_DIR / "all_music_analysis_summary.json"
    save_json_result(summary_result, summary_json_path)

    write_progress(job_id, {
        "status": "completed",
        "total_files": total_files,
        "current_file_index": 0,
        "processed_count": processed_count,
        "current_step": FILE_PROGRESS_TEXT[lang]["all_completed"],
        "files": make_progress_files(
            audio_files,
            processed_count=total_files,
            failed_indexes=failed_indexes,
        ),
        "result": summary_result,
        "error": None,
        "cancel_requested": False,
        "cancel_reason": None,
        "language": lang,
    })

    print("\n" + "=" * 100)
    print("Final Summary")
    print("=" * 100)
    print(f"Total File Count: {summary_result['total_file_count']}")
    print(
        f"Total Music Duration: {summary_result['total_music_duration']['seconds']} sec "
        f"({summary_result['total_music_duration']['text']})"
    )
    print(
        f"Total Program Execution Time: {summary_result['total_program_execution_time']['seconds']} sec "
        f"({summary_result['total_program_execution_time']['text']})"
    )
    print(f"Summary JSON Path: {summary_json_path.resolve()}")
    print("=" * 100)

    return summary_result