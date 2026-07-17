from __future__ import annotations

from collections import deque
from pathlib import Path
from threading import Lock
import time

import cv2
import mediapipe as mp
import numpy as np
from flask import Response, render_template, stream_with_context
from tensorflow.keras.models import load_model

from . import bp


ACTIONS = ("best", "ok", "yeah", "heart")
ACTION_LABELS = {
    "best": "BEST",
    "ok": "OK",
    "yeah": "YEAH",
    "heart": "HEART",
}
ACTION_ICONS = {
    "best": "good-job.png",
    "ok": "ok.png",
    "yeah": "lovely.png",
    "heart": "heart.png",
}

SEQ_LENGTH = 30
FEATURE_SIZE = 99  # 손 관절 21 * 4 + 관절 각도 15
CONFIDENCE_THRESHOLD = 0.90
STABLE_FRAME_COUNT = 3

_MODEL = None
_MODEL_LOCK = Lock()
_CAMERA_LOCK = Lock()

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

@bp.get("/", endpoint="show")
def show():
    return render_template("signcue.html")


@bp.get("/cam", endpoint="cam")
def cam():
    return Response(
        stream_with_context(_generate_frames()),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )

def _static_dir() -> Path:
    if not bp.static_folder:
        raise RuntimeError("signcue static 폴더가 설정되지 않았습니다.")
    return Path(bp.static_folder)


def _find_model_path() -> Path:
    static_dir = _static_dir()
    candidates = (
        static_dir / "model" / "model.h5",
    )
    print(f"=================={candidates}==================")

    for path in candidates:
        if path.exists():
            return path

    expected = " 또는 ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "학습된 model.h5를 찾을 수 없습니다. "
        f"다음 위치 중 한 곳에 넣어주세요: {expected}"
    )


def _get_model():
    global _MODEL

    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                model_path = _find_model_path()
                _MODEL = load_model(model_path, compile=False)

                input_shape = getattr(_MODEL, "input_shape", None)
                if input_shape and len(input_shape) >= 3:
                    model_seq_length = input_shape[-2]
                    model_feature_size = input_shape[-1]

                    if model_seq_length not in (None, SEQ_LENGTH):
                        raise ValueError(
                            "모델 sequence 길이가 코드와 다릅니다. "
                            f"모델={model_seq_length}, 코드={SEQ_LENGTH}"
                        )

                    if model_feature_size not in (None, FEATURE_SIZE):
                        raise ValueError(
                            "모델 feature 수가 코드와 다릅니다. "
                            f"모델={model_feature_size}, 코드={FEATURE_SIZE}"
                        )

    return _MODEL


def _read_icon(path: Path, size: int = 92):
    if not path.exists():
        return None

    icon = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if icon is None:
        return None

    return cv2.resize(icon, (size, size), interpolation=cv2.INTER_AREA)


def _load_icons() -> dict[str, np.ndarray | None]:
    icon_dir = _static_dir() / "icon"
    return {
        action: _read_icon(icon_dir / filename)
        for action, filename in ACTION_ICONS.items()
    }


def _overlay_rgba_center(
    frame: np.ndarray,
    overlay: np.ndarray | None,
    center_x: int,
    center_y: int,
) -> None:
    """화면 가장자리에서도 오류 없이 PNG를 합성한다."""
    if overlay is None or overlay.ndim != 3:
        return

    overlay_h, overlay_w = overlay.shape[:2]
    x1 = center_x - overlay_w // 2
    y1 = center_y - overlay_h // 2
    x2 = x1 + overlay_w
    y2 = y1 + overlay_h

    frame_h, frame_w = frame.shape[:2]
    clip_x1 = max(0, x1)
    clip_y1 = max(0, y1)
    clip_x2 = min(frame_w, x2)
    clip_y2 = min(frame_h, y2)

    if clip_x1 >= clip_x2 or clip_y1 >= clip_y2:
        return

    overlay_x1 = clip_x1 - x1
    overlay_y1 = clip_y1 - y1
    overlay_x2 = overlay_x1 + (clip_x2 - clip_x1)
    overlay_y2 = overlay_y1 + (clip_y2 - clip_y1)

    cropped = overlay[overlay_y1:overlay_y2, overlay_x1:overlay_x2]
    roi = frame[clip_y1:clip_y2, clip_x1:clip_x2]

    if cropped.shape[2] == 4:
        alpha = cropped[:, :, 3:4].astype(np.float32) / 255.0
        foreground = cropped[:, :, :3].astype(np.float32)
        background = roi.astype(np.float32)
        blended = foreground * alpha + background * (1.0 - alpha)
        frame[clip_y1:clip_y2, clip_x1:clip_x2] = blended.astype(np.uint8)
    else:
        frame[clip_y1:clip_y2, clip_x1:clip_x2] = cropped[:, :, :3]


def _extract_features(hand_landmarks) -> np.ndarray | None:
    joint = np.zeros((21, 4), dtype=np.float32)

    for index, landmark in enumerate(hand_landmarks.landmark):
        joint[index] = (
            landmark.x,
            landmark.y,
            landmark.z,
            getattr(landmark, "visibility", 0.0),
        )

    parent = joint[
        [0, 1, 2, 3, 0, 5, 6, 7, 0, 9, 10, 11, 0, 13, 14, 15, 0, 17, 18, 19],
        :3,
    ]
    child = joint[
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
        :3,
    ]

    vectors = child - parent
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)

    # 0으로 나누어 NaN이 생기면 모델 입력이 깨지므로 해당 프레임은 건너뛴다.
    if np.any(norms < 1e-8):
        return None

    vectors = vectors / norms

    dot = np.einsum(
        "nt,nt->n",
        vectors[[0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17, 18]],
        vectors[[1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15, 17, 18, 19]],
    )
    dot = np.clip(dot, -1.0, 1.0)
    angles = np.degrees(np.arccos(dot)).astype(np.float32)

    features = np.concatenate((joint.flatten(), angles)).astype(np.float32)

    if features.shape[0] != FEATURE_SIZE or not np.all(np.isfinite(features)):
        return None

    return features


def _predict_action(model, sequence: deque[np.ndarray]):
    input_data = np.expand_dims(
        np.asarray(sequence, dtype=np.float32),
        axis=0,
    )

    prediction = model(input_data, training=False)
    if hasattr(prediction, "numpy"):
        prediction = prediction.numpy()

    probabilities = np.asarray(prediction).squeeze()
    predicted_index = int(np.argmax(probabilities))
    confidence = float(probabilities[predicted_index])

    return ACTIONS[predicted_index], confidence


def _draw_status(
    frame: np.ndarray,
    action: str | None,
    confidence: float,
    hand_detected: bool,
) -> None:
    height, width = frame.shape[:2]

    cv2.rectangle(frame, (0, 0), (width, 82), (18, 24, 38), -1)
    cv2.putText(
        frame,
        "BEST  |  OK  |  YEAH  |  HEART",
        (28, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    if action:
        status = f"Action: {ACTION_LABELS[action]}  ({confidence * 100:.1f}%)"
        status_color = (70, 230, 150)
    elif hand_detected:
        status = "Recognising gesture..."
        status_color = (255, 220, 110)
    else:
        status = "Show one hand to the camera"
        status_color = (210, 220, 235)

    cv2.putText(
        frame,
        status,
        (28, height - 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.78,
        status_color,
        2,
        cv2.LINE_AA,
    )


def _save_capture(frame: np.ndarray, action: str) -> None:
    capture_dir = _static_dir() / "captures"
    capture_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{action}_{int(time.time() * 1000)}.jpg"
    cv2.imwrite(str(capture_dir / filename), frame)


def _generate_frames():
    model = _get_model()
    icons = _load_icons()

    # 같은 Flask 프로세스에서 카메라 스트림이 두 번 열리는 것을 방지한다.
    with _CAMERA_LOCK:
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            raise RuntimeError("카메라를 열 수 없습니다.")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        sequence: deque[np.ndarray] = deque(maxlen=SEQ_LENGTH)
        recent_actions: deque[str] = deque(maxlen=STABLE_FRAME_COUNT)
        stable_action: str | None = None
        stable_confidence = 0.0
        last_capture_at = 0.0
        last_captured_action: str | None = None

        hands_detector = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands_detector.process(rgb)

                hand_detected = bool(result.multi_hand_landmarks)
                frame_action: str | None = None
                frame_confidence = 0.0
                index_finger = None

                if result.multi_hand_landmarks:
                    hand_landmarks = result.multi_hand_landmarks[0]
                    height, width = frame.shape[:2]
                    finger = hand_landmarks.landmark[8]
                    index_finger = (int(finger.x * width), int(finger.y * height))

                    features = _extract_features(hand_landmarks)
                    if features is not None:
                        sequence.append(features)

                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                        mp_drawing_styles.get_default_hand_landmarks_style(),
                        mp_drawing_styles.get_default_hand_connections_style(),
                    )

                    if len(sequence) == SEQ_LENGTH:
                        predicted_action, confidence = _predict_action(model, sequence)

                        if confidence >= CONFIDENCE_THRESHOLD:
                            recent_actions.append(predicted_action)
                            frame_confidence = confidence

                            if (
                                len(recent_actions) == STABLE_FRAME_COUNT
                                and len(set(recent_actions)) == 1
                            ):
                                frame_action = predicted_action
                                stable_action = predicted_action
                                stable_confidence = confidence
                        else:
                            recent_actions.clear()

                else:
                    # 손이 사라진 뒤 이전 동작이 계속 남지 않도록 초기화한다.
                    sequence.clear()
                    recent_actions.clear()
                    stable_action = None
                    stable_confidence = 0.0

                display_action = frame_action or stable_action
                display_confidence = frame_confidence or stable_confidence

                if display_action and index_finger:
                    offsets = {
                        "best": (105, -55),
                        "ok": (110, 0),
                        "yeah": (0, -70),
                        "heart": (0, -70),
                    }
                    offset_x, offset_y = offsets[display_action]
                    icon = icons.get(display_action)

                    if icon is not None:
                        _overlay_rgba_center(
                            frame,
                            icon,
                            index_finger[0] + offset_x,
                            index_finger[1] + offset_y,
                        )
                    else:
                        cv2.putText(
                            frame,
                            ACTION_LABELS[display_action],
                            (
                                max(10, index_finger[0] + offset_x - 35),
                                max(50, index_finger[1] + offset_y),
                            ),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.8,
                            (255, 0, 255),
                            2,
                            cv2.LINE_AA,
                        )

                    # 같은 동작을 매 프레임 저장하지 않고, 2초 간격으로 한 장만 저장한다.
                    now = time.time()
                    if (
                        display_action != last_captured_action
                        or now - last_capture_at >= 2.0
                    ):
                        _save_capture(frame, display_action)
                        last_capture_at = now
                        last_captured_action = display_action

                _draw_status(
                    frame,
                    display_action,
                    display_confidence,
                    hand_detected,
                )

                encoded, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 86],
                )
                if not encoded:
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + buffer.tobytes()
                    + b"\r\n"
                )
        finally:
            hands_detector.close()
            cap.release()

