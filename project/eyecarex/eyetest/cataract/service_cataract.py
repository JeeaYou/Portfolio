# project/eyecarex/eyetest/cataract/service_cataract.py

from flask import render_template, Response, current_app
from . import bp

import cv2
import time
import datetime
import os
import pandas as pd
import shutil

from cvzone.FaceMeshModule import FaceMeshDetector
from cvzone.HandTrackingModule import HandDetector
from PIL import ImageFont

from ...common.services import (
    get_lang,
    overlay_png,
    text_box,
    overlay_test_result_screen,
    draw_banner_with_text
)

from .static.models.cataract_predict import image_test

lang = get_lang()

@bp.get("/", endpoint="show")
def show():
    return render_template("cataract.html", lang=lang)


def read_image(path, flag=cv2.IMREAD_UNCHANGED, name="이미지"):
    img = cv2.imread(path, flag)

    if img is None:
        raise FileNotFoundError(f"Can't read {name}: {path}")

    return img


def crop_safe(frame, x1, y1, x2, y2):
    h, w = frame.shape[:2]

    x1 = max(0, min(x1, w))
    x2 = max(0, min(x2, w))
    y1 = max(0, min(y1, h))
    y2 = max(0, min(y2, h))

    if x2 <= x1 or y2 <= y1:
        return None

    return frame[y1:y2, x1:x2]


@bp.get("/cam")
def cam():
    eyecarex_dir = current_app.blueprints["eyecarex"].static_folder
    curr_dir = bp.static_folder

    def gen():
        image_dir = os.path.join(curr_dir, "image")

        if os.path.exists(image_dir):
            shutil.rmtree(image_dir)

        os.makedirs(image_dir, exist_ok=True)

        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            raise RuntimeError("Can't open camera.")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if width <= 0 or height <= 0:
            width, height = 1280, 720

        w2, h2 = width // 2, height // 2

        btn_size = width // 10
        half = int(btn_size * 0.4)

        # MediaPipe 직접 사용 금지
        # 기존 mp.solutions.face_detection / mp.solutions.hands 대신 cvzone 사용
        face_detector = FaceMeshDetector(maxFaces=1)
        hand_detector = HandDetector(maxHands=1, detectionCon=0.5)

        # ---------- 경로 ----------
        font_path = os.path.join(eyecarex_dir, "fonts", "H2GSRB.TTF")
        bg_path = os.path.join(eyecarex_dir, "image", "background.jpg")

        # 기존 button/logo.png 아님
        # project/eyecarex/static/image/logo.png
        logo_path = os.path.join(eyecarex_dir, "image", "logo.png")

        face_path = os.path.join(eyecarex_dir, "button", "face.png")

        # ---------- 리소스 ----------
        if not os.path.exists(font_path):
            raise FileNotFoundError(f"Can't find font file: {font_path}")

        font = ImageFont.truetype(font_path, 20)

        background_raw = read_image(bg_path, cv2.IMREAD_COLOR, "background 이미지")
        logo = read_image(logo_path, cv2.IMREAD_UNCHANGED, "logo 이미지")
        face_img = read_image(face_path, cv2.IMREAD_UNCHANGED, "face 이미지")

        background = cv2.resize(background_raw, (width, height))

        name = "백내장"
        result_list = []

        timeStart = time.time()
        testEnd = False
        captured = False

        try:
            while True:
                ok, frame = cap.read()

                if not ok:
                    break

                frame = cv2.flip(frame, 1)
                frame, faces = face_detector.findFaceMesh(frame, draw=False)

                hands, frame = hand_detector.findHands(
                    frame,
                    draw=False,
                    flipType=False
                )

                # 얼굴이 감지되면 FaceMesh 좌표로 양쪽 눈 영역 추출
                if faces:
                    face_lm = faces[0]

                    # MediaPipe FaceMesh 기준 눈 주변 대표 인덱스
                    # 오른쪽 눈: 33, 133
                    # 왼쪽 눈: 362, 263
                    try:
                        r1 = face_lm[33]
                        r2 = face_lm[133]
                        l1 = face_lm[362]
                        l2 = face_lm[263]

                        r_cx = int((r1[0] + r2[0]) / 2)
                        r_cy = int((r1[1] + r2[1]) / 2)

                        l_cx = int((l1[0] + l2[0]) / 2)
                        l_cy = int((l1[1] + l2[1]) / 2)

                        right = crop_safe(
                            frame,
                            r_cx - 60,
                            r_cy - 45,
                            r_cx + 60,
                            r_cy + 45
                        )

                        left = crop_safe(
                            frame,
                            l_cx - 60,
                            l_cy - 45,
                            l_cx + 60,
                            l_cy + 45
                        )

                        overlay_png(
                            frame,
                            w2,
                            h2,
                            int(h2 // 2),
                            int(h2 // 2),
                            face_img
                        )

                    except Exception:
                        right = None
                        left = None

                    # 손 감지 후 주먹 동작 비슷한 조건이면 촬영
                    if hands and not captured and right is not None and left is not None:
                        hand = hands[0]
                        lmList = hand.get("lmList", [])

                        if len(lmList) > 8:
                            # 손가락 끝과 손바닥 기준점 거리로 주먹 여부 판단
                            index_tip_y = lmList[8][1]
                            index_base_y = lmList[5][1]
                            wrist_y = lmList[0][1]

                            dist_tip = abs(index_tip_y - wrist_y)
                            dist_base = abs(index_base_y - wrist_y)

                            # 기존 코드의 dist == dist2는 너무 엄격해서 거의 안 맞을 수 있음
                            # 그래서 약간의 허용 범위를 둠
                            if abs(dist_tip - dist_base) <= 10:
                                now = datetime.datetime.now().strftime("%d_%H-%M-%S")

                                right_name = os.path.join(
                                    image_dir,
                                    f"right_image_{now}.jpg"
                                )

                                left_name = os.path.join(
                                    image_dir,
                                    f"left_image_{now}.jpg"
                                )

                                cv2.imwrite(right_name, right)
                                right_class_name, right_score = image_test(right_name)

                                result_list.append({
                                    "eye": "오른쪽눈" if lang == "ko" else "Right Eye",
                                    "tf": right_class_name,
                                    "pecent": f"{right_score}%",
                                    "image": right_name
                                })

                                cv2.imwrite(left_name, left)
                                left_class_name, left_score = image_test(left_name)

                                result_list.append({
                                    "eye": "왼쪽눈" if lang == "ko" else "Left Eye",
                                    "tf": left_class_name,
                                    "percent": f"{left_score}%",
                                    "image": left_name
                                })

                                csv_dir = os.path.join(eyecarex_dir, "csv_file")
                                os.makedirs(csv_dir, exist_ok=True)

                                csv_path = os.path.join(csv_dir, f"{name}.csv")

                                df = pd.DataFrame(result_list)
                                df.to_csv(csv_path, index=False)

                                captured = True
                                testEnd = True
                                timeStart = time.time()

                # ---------- 공통 UI ----------
                draw_banner_with_text(
                    frame,
                    width,
                    height,
                    font,
                    "카메라를 보고 손을 펼친 뒤, 주먹을 쥐면 촬영됩니다." if lang == "ko" else "Look at the camera, open your hand, and make a fist to take a picture."
                )

                overlay_png(
                    frame,
                    20,
                    20,
                    half // 2,
                    half // 2,
                    logo
                )

                if testEnd:
                    should_break = overlay_test_result_screen(
                        frame,
                        background,
                        name,
                        result_list,
                        timeStart,
                        height,
                        w2,
                        h2,
                        font,
                        eyecarex_dir
                    )

                    if should_break:
                        break

                ok2, buf = cv2.imencode(".jpg", frame)

                if not ok2:
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + buf.tobytes()
                    + b"\r\n"
                )

        finally:
            cap.release()

    return Response(
        gen(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )