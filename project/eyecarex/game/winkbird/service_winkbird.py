# project/eyecarex/game/winkbird/service_winkbird.py

from flask import render_template, Response, current_app
from . import bp

import os
import cv2
import time
import datetime
import random
import numpy as np
import pandas as pd
import cvzone

from cvzone.FaceMeshModule import FaceMeshDetector
from cvzone.HandTrackingModule import HandDetector
from PIL import ImageFont

from ...common.services import (
    get_lang,
    load_texts,
    overlay_png,
    overlay_jpg,
    text_box,
    draw_banner_with_text
)

texts = {
    "winkbird_cam_start_touch": "START 버튼에 2초간 터치하세요.",
    "winkbird_cam_guide": "{totalTime}초 동안 깜빡임으로 새를 잡아보세요.",
    "winkbird_eye_closed": "CLOSED",
    "winkbird_eye_open": "OPEN",
    "winkbird_score_label": "Score: {count}",
    "winkbird_time_label": "Time: {remaining}",
    "winkbird_game_over": "Game Over",
    "winkbird_your_score": "Your Score: {count}",
    "winkbird_restart_desc": "게임 다시 시작하려면 다시하기 누르세요.",
    "winkbird_error_camera": "카메라를 열 수 없습니다.",
    "winkbird_error_font": "폰트 파일을 찾을 수 없습니다: {font_path}",
}

@bp.get("/", endpoint="show")
def show():

    lang = get_lang()
    msg = load_texts(lang, texts)

    return render_template("winkbird.html",
                           lang = lang,
                           msg = msg)


def read_image(path, flag=cv2.IMREAD_UNCHANGED, name="이미지"):
    img = cv2.imread(path, flag)

    if img is None:
        raise FileNotFoundError(f"{name}를 읽을 수 없습니다: {path}")

    return img


def get_text_size(text, font):
    text = str(text)
    bbox = font.getbbox(text)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return w, h


def draw_center_text(frame, text, font, color, y=None):
    h, w = frame.shape[:2]
    text_w, text_h = get_text_size(text, font)

    x = (w - text_w) // 2

    if y is None:
        y = (h - text_h) // 2

    text_box(
        frame,
        int(x),
        int(y),
        str(text),
        font,
        color
    )


@bp.get("/cam")
def cam():

    lang = get_lang()
    msg = load_texts(lang, texts)

    eyecarex_dir = current_app.blueprints["eyecarex"].static_folder
    game_dir = current_app.blueprints["eyecarex.game"].static_folder
    curr_dir = bp.static_folder

    nowDatetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def gen():
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            raise RuntimeError(msg["winkbird_error_camera"])

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720

        w2, h2 = width // 2, height // 2
        btn_size = width // 10

        # FaceMesh는 cvzone 사용
        detector = FaceMeshDetector(maxFaces=1)

        # mediapipe 직접 사용 금지
        # mp.solutions.hands 대신 cvzone HandDetector 사용
        hand_detector = HandDetector(
            maxHands=2,
            detectionCon=0.5
        )

        # ---------- 리소스 경로 ----------
        font_path = os.path.join(eyecarex_dir, "fonts", "H2GSRB.TTF")

        if not os.path.exists(font_path):
            raise FileNotFoundError(msg["winkbird_error_font"].format(font_path=font_path))

        font_small = ImageFont.truetype(font_path, 50)
        font_big = ImageFont.truetype(font_path, max(24, width // 5))
        font_timer = ImageFont.truetype(font_path, h2 // 8)
        font_gameov = ImageFont.truetype(font_path, height // 10)

        bg_path = os.path.join(eyecarex_dir, "image", "background.jpg")
        logo_path = os.path.join(eyecarex_dir, "image", "logo.png")
        tbx_path = os.path.join(eyecarex_dir, "image", "textbox.png")
        start_path = os.path.join(game_dir, "image", "start.png")

        # ---------- 리소스 읽기 ----------
        background_raw = read_image(bg_path, cv2.IMREAD_COLOR, "background 이미지")
        logo = read_image(logo_path, cv2.IMREAD_UNCHANGED, "logo 이미지")
        textbox_img = read_image(tbx_path, cv2.IMREAD_UNCHANGED, "textbox 이미지")
        start_img = read_image(start_path, cv2.IMREAD_UNCHANGED, "start 버튼 이미지")

        background = cv2.resize(background_raw, (width, height))

        # ---------- 게임 오브젝트 로딩 ----------
        bird_dir = os.path.join(curr_dir, "image")

        files = [
            f for f in (os.listdir(bird_dir) if os.path.isdir(bird_dir) else [])
            if f.lower().endswith(".png")
        ]

        catch = []

        for fname in files:
            obj_path = os.path.join(bird_dir, fname)
            obj = cv2.imread(obj_path, cv2.IMREAD_UNCHANGED)

            if obj is not None:
                obj = cv2.resize(obj, (btn_size, btn_size))
                catch.append(obj)

        if not catch:
            catch = [
                255 * np.ones((btn_size, btn_size, 4), dtype=np.uint8)
            ]

        current_obj = catch[0]
        pos = [random.randint(0, max(0, width - btn_size)), 0]

        BASE_SPEED = 5       # 시작 속도
        MAX_SPEED = 18       # 최대 속도
        SPEED_STEP = 2       # 한 번에 빨라지는 정도
        SPEED_UP_EVERY = 5   # 몇 초마다 빨라질지

        speed = BASE_SPEED
        count = 0

        # ---------- 상태 변수 ----------
        press_start = None
        HOLD_SEC = 2.0

        started = False
        counting_down = False
        countdown_end = None

        timeStart = None
        endTime = None

        gameOver = False
        saved_score = False

        totalTime = 30

        BLINK_FRAMES = 35
        EYE_CLOSE = BLINK_FRAMES * 0.72
        EYE_OPEN = BLINK_FRAMES * 0.88

        blink_in_progress = False
        closed_frames = 0

        ratioList = []
        userID = "000000001"
        guide = msg["winkbird_cam_guide"].format(totalTime=totalTime)


        def reset_object():
            pos[0] = random.randint(0, max(0, width - btn_size))
            pos[1] = 0
            return catch[random.randrange(len(catch))]

        def save_game_score():
            csv_dir = os.path.join(eyecarex_dir, "csv_file")
            os.makedirs(csv_dir, exist_ok=True)

            csv_path = os.path.join(csv_dir, "게임.csv")

            row = {
                "ID": userID,
                "시간": nowDatetime,
                "점수": str(count)
            }

            df = pd.DataFrame([row])

            if os.path.exists(csv_path):
                df.to_csv(
                    csv_path,
                    mode="a",
                    index=False,
                    header=False,
                    encoding="utf-8-sig"
                )
            else:
                df.to_csv(
                    csv_path,
                    index=False,
                    encoding="utf-8-sig"
                )

        try:
            while True:
                ok, frame = cap.read()

                if not ok:
                    break

                frame = cv2.flip(frame, 1)
                hands, frame = hand_detector.findHands(
                    frame,
                    draw=False,
                    flipType=False
                )

                # ---------- 아직 시작 전 ----------
                if not started and not counting_down:
                    draw_banner_with_text(
                        frame,
                        width,
                        height,
                        font_small,
                        msg["winkbird_cam_start_touch"]
                    )

                    overlay_png(
                        frame,
                        60,
                        60,
                        btn_size // 4,
                        btn_size // 4,
                        logo
                    )

                    half_w = width // 5
                    half_h = height // 5

                    overlay_png(
                        frame,
                        w2,
                        h2,
                        half_w,
                        half_h,
                        start_img
                    )

                    start_btn = (
                        w2 - half_w,
                        h2 - half_h,
                        w2 + half_w,
                        h2 + half_h
                    )

                    touching = False

                    if hands:
                        for hand in hands:
                            lmList = hand.get("lmList", [])

                            if len(lmList) > 8:
                                fx = lmList[8][0]
                                fy = lmList[8][1]

                                cv2.circle(
                                    frame,
                                    (fx, fy),
                                    5,
                                    (255, 0, 255),
                                    -1,
                                    cv2.LINE_AA
                                )

                                if (
                                    start_btn[0] <= fx <= start_btn[2]
                                    and start_btn[1] <= fy <= start_btn[3]
                                ):
                                    touching = True
                                    break

                    if touching:
                        if press_start is None:
                            press_start = time.time()

                        held = time.time() - press_start
                        progress = min(360, int(360 * (held / HOLD_SEC)))

                        cv2.ellipse(
                            frame,
                            (w2, h2),
                            (half_w, half_h),
                            0,
                            0,
                            progress,
                            (255, 0, 255),
                            8
                        )

                        if held >= HOLD_SEC:
                            counting_down = True
                            countdown_end = time.time() + 5.0
                            press_start = None

                    else:
                        press_start = None

                # ---------- 카운트다운 ----------
                elif counting_down and not started:
                    draw_banner_with_text(
                        frame,
                        width,
                        height,
                        font_small,
                        guide
                    )

                    remain = countdown_end - time.time()

                    if remain > 0:
                        sec = int(remain) + 1

                        draw_center_text(
                            frame,
                            str(sec),
                            font_big,
                            (255, 0, 255),
                            y=None
                        )

                    else:
                        started = True
                        timeStart = time.time()
                        endTime = timeStart + float(totalTime)
                        counting_down = False

                # ---------- 게임 진행 ----------
                elif not gameOver:
                    draw_banner_with_text(
                        frame,
                        width,
                        height,
                        font_small,
                        guide
                    )

                    overlay_png(
                        frame,
                        60,
                        60,
                        btn_size // 4,
                        btn_size // 4,
                        logo
                    )

                    remaining = int(endTime - time.time())
                    gameOn = remaining >= 0

                    elapsed = time.time() - timeStart

                    speed = min(
                        MAX_SPEED,
                        BASE_SPEED + int(elapsed // SPEED_UP_EVERY) * SPEED_STEP
                    )

                    if gameOn:
                        frame, faces = detector.findFaceMesh(
                            frame,
                            draw=False
                        )

                        # 오브젝트 이동
                        pos[1] += speed

                        if pos[1] > height - btn_size:
                            current_obj = reset_object()

                        else:
                            if (
                                0 <= pos[0] <= width - btn_size
                                and 0 <= pos[1] <= height - btn_size
                            ):
                                frame = cvzone.overlayPNG(
                                    frame,
                                    current_obj,
                                    pos
                                )
                            else:
                                current_obj = reset_object()

                        if faces:
                            face = faces[0]

                            upDown, _ = detector.findDistance(face[159], face[23])
                            leftRight, _ = detector.findDistance(face[130], face[243])
                            ratio = int((upDown / leftRight) * 100) if leftRight else 999

                            ratioList.append(ratio)

                            if len(ratioList) > 3 : ratioList.pop(0)
                            ratioAvg = sum(ratioList) / len(ratioList)

                            closed_frames = closed_frames + 1 if ratioAvg < EYE_CLOSE else 0

                            # # 오른쪽 눈 옆에 눈 상태 문자 표시
                            # if ratioAvg < EYE_CLOSE:
                            #     eye_state_text = msg["winkbird_eye_closed"]
                            #     eye_state_color = (0, 0, 255)
                            # else:
                            #     eye_state_text = msg["winkbird_eye_open"]
                            #     eye_state_color = (0, 255, 0)

                            # right_eye_x = int(face[263][0])
                            # right_eye_y = int(face[263][1])

                            # text_w, text_h = get_text_size(eye_state_text, font_small)

                            # text_x = right_eye_x + 25
                            # text_y = right_eye_y - 35

                            # # 화면 밖으로 나가지 않게 보정
                            # text_x = max(10, min(text_x, width - text_w - 10))
                            # text_y = max(20, min(text_y, height - text_h - 10))

                            # text_box(
                            #     frame,
                            #     text_x,
                            #     text_y,
                            #     eye_state_text,
                            #     font_small,
                            #     eye_state_color
                            # )

                            # 깜빡임 시작
                            if ratioAvg < EYE_CLOSE:
                                blink_in_progress = True
                            # 깜빡임 끝 (다시 열림)
                            elif blink_in_progress and (ratioAvg > EYE_OPEN):
                                current_obj = reset_object()
                                count += 1
                                blink_in_progress = False

                        # 하단 UI
                        overlay_png(
                            frame,
                            int(width * 0.16),
                            int(height * 0.82),
                            width // 7,
                            height // 15,
                            textbox_img
                        )

                        text_box(
                            frame,
                            int(btn_size * 0.75),
                            int(height * 0.8),
                            msg["winkbird_score_label"].format(count=count),
                            font_small,
                            (0, 0, 0)
                        )

                        text_box(
                            frame,
                            width - 350,
                            20,
                            msg["winkbird_time_label"].format(remaining=remaining),
                            font_timer,
                            (255, 0, 255)
                        )

                    else:
                        gameOver = True

                # ---------- 게임오버 ----------
                else:
                    overlay_jpg(
                        frame,
                        background,
                        w2,
                        h2
                    )

                    draw_center_text(
                        frame,
                        msg["winkbird_game_over"],
                        font_gameov,
                        (0, 0, 0),
                        y=int(height * 0.30)
                    )

                    draw_center_text(
                        frame,
                        msg["winkbird_your_score"].format(count=count),
                        font_small,
                        (0, 0, 0),
                        y=int(height * 0.58)
                    )

                    draw_center_text(
                        frame,
                        msg["winkbird_restart_desc"],
                        font_small,
                        (0, 0, 0),
                        y=int(height * 0.70)
                    )

                    # 점수는 한 번만 저장
                    if not saved_score:
                        save_game_score()
                        saved_score = True

                # ---------- 스트림 전송 ----------
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