# project/eyecarex/eyetest/colortest/service_colortest.py

from flask import render_template, Response, current_app
from . import bp

import cv2
import time
import datetime
import os

from cvzone.FaceMeshModule import FaceMeshDetector
from cvzone.HandTrackingModule import HandDetector
from PIL import ImageFont

from ...common.services import (
    get_lang,
    overlay_png,
    overlay_jpg,
    text_box,
    save_results,
    overlay_next_test_screen,
    overlay_test_result_screen,
    draw_banner_with_text
)

lang = get_lang()

@bp.get("/", endpoint="show")
def show():
    return render_template("colortest.html", lang=lang)


# ---------- 헬퍼 ----------
def hit(pt, center, half):
    return abs(pt[0] - center[0]) < half and abs(pt[1] - center[1]) < half


def decide_answer(seq3, lang="ko"):
    a, b, btn = seq3

    if (a, b, btn) == (97, 74, 26):
        return "정상" if lang == "ko" else "Normal"

    if btn == 2:
        return "녹색맹" if lang == "ko" else "Deuteranopia"

    if btn == 6:
        return "적색맹" if lang == "ko" else "Protanopia"

    if b != 74 or btn != 26:
        return "적녹색맹" if lang == "ko" else "Red-Green Color Blindness"

    return "색각이상" if lang == "ko" else "Color Vision Deficiency"


def read_image(path, flag=cv2.IMREAD_UNCHANGED, name="이미지"):
    img = cv2.imread(path, flag)

    if img is None:
        raise FileNotFoundError(f"{name}를 읽을 수 없습니다: {path}")

    return img


@bp.get("/cam")
def cam():

    lang = get_lang()


    # project/eyecarex/static
    eyecarex_dir = current_app.blueprints["eyecarex"].static_folder

    # project/eyecarex/eyetest/colortest/static
    curr_dir = bp.static_folder

    def gen():
        nowDatetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

        # eyevision처럼 cvzone 사용
        face_detector = FaceMeshDetector(maxFaces=1)

        # mediapipe 직접 사용하지 않고 cvzone HandDetector 사용
        hand_detector = HandDetector(
            maxHands=1,
            detectionCon=0.5
        )

        # ---------- 경로 ----------
        font_path = os.path.join(eyecarex_dir, "fonts", "H2GSRB.TTF")
        bg_path = os.path.join(eyecarex_dir, "image", "background.jpg")

        # 중요: button/logo.png 아님
        # project/eyecarex/static/image/logo.png
        logo_path = os.path.join(eyecarex_dir, "image", "logo.png")

        tbx_path = os.path.join(eyecarex_dir, "image", "textbox.png")
        img_test_path = os.path.join(curr_dir, "image", "colortest.jpg")

        # ---------- 리소스 로드 ----------
        if not os.path.exists(font_path):
            raise FileNotFoundError(f"Can't find font file: {font_path}")

        font = ImageFont.truetype(font_path, 20)

        background_raw = read_image(bg_path, cv2.IMREAD_COLOR, "background 이미지")
        logo = read_image(logo_path, cv2.IMREAD_UNCHANGED, "logo 이미지")
        img_textbox = read_image(tbx_path, cv2.IMREAD_UNCHANGED, "textbox 이미지")
        img_test = read_image(img_test_path, cv2.IMREAD_COLOR, "색각검사 이미지")

        background = cv2.resize(background_raw, (width, height))

        h_img, w_img = img_test.shape[:2]
        img_test = cv2.resize(img_test, (w2, round(h_img * w2 / w_img)))

        # ---------- 선택지 버튼 ----------
        buttons = [
            {
                "val": 2,
                "pos": (int(width * 0.30), int(height * 0.70)),
                "path": os.path.join(curr_dir, "image", "2.png")
            },
            {
                "val": 6,
                "pos": (int(width * 0.40), int(height * 0.70)),
                "path": os.path.join(curr_dir, "image", "6.png")
            },
            {
                "val": 26,
                "pos": (int(width * 0.50), int(height * 0.70)),
                "path": os.path.join(curr_dir, "image", "26.png")
            },
            {
                "val": 74,
                "pos": (int(width * 0.60), int(height * 0.70)),
                "path": os.path.join(curr_dir, "image", "74.png")
            },
            {
                "val": 97,
                "pos": (int(width * 0.70), int(height * 0.70)),
                "path": os.path.join(curr_dir, "image", "97.png")
            },
        ]

        for btn in buttons:
            btn["img"] = read_image(
                btn["path"],
                cv2.IMREAD_UNCHANGED,
                f"{btn['val']} 버튼 이미지"
            )

        # ---------- 상태 변수 ----------
        counter = 0
        seq = []
        selected_btns = []

        result_list = []

        next_test = False
        testEnd = False

        eye = '오른쪽눈' if lang == 'ko'  else 'Left Eye'
        timeStart = time.time()

        disease_name = "색각" if lang == 'ko' else "Color Vision"
        guide_message = (
            "제시된 그림 3개를 각각 보시고,\n"
            "각 그림 속 숫자가 무엇인지 짚어주세요."
        ) if lang == 'ko' else (
            "Look at the 3 presented pictures,\n"
            "and point out what number you see in each picture."
        )

        selectionSpeed = 8
        userID = "000000001"

        try:
            while True:
                ok, frame = cap.read()

                if not ok:
                    break

                # 얼굴 메시 처리
                frame, _ = face_detector.findFaceMesh(frame, draw=False)

                # 손 인식 처리
                hands, frame = hand_detector.findHands(
                    frame,
                    draw=False,
                    flipType=False
                )

                if hands:
                    hand = hands[0]
                    lmList = hand.get("lmList", [])

                    if len(lmList) > 8:
                        fx, fy = lmList[8][0], lmList[8][1]

                        cv2.circle(
                            frame,
                            (fx, fy),
                            5,
                            (255, 0, 255),
                            -1,
                            cv2.LINE_AA
                        )

                        hit_any = False

                        for btn in buttons:
                            if hit((fx, fy), btn["pos"], half):
                                hit_any = True
                                counter += 1

                                progress = counter * selectionSpeed

                                cv2.ellipse(
                                    frame,
                                    btn["pos"],
                                    (half, half),
                                    0,
                                    0,
                                    min(progress, 360),
                                    (255, 0, 255),
                                    10
                                )

                                if progress >= 360:
                                    seq.append(btn["val"])
                                    selected_btns.append(btn["val"])

                                    counter = 0
                                    timeStart = time.time()

                                break

                        if not hit_any:
                            counter = 0

                        # 3개 선택 완료 시 판정
                        if len(seq) == 3:
                            answer = decide_answer(tuple(seq))
                            seq.clear()

                            result_list = save_results(
                                userID,
                                nowDatetime,
                                eye,
                                answer,
                                result_list,
                                disease_name,
                                eyecarex_dir
                            )

                            timeStart = time.time()

                            if len(result_list) == 1 and (eye == "오른쪽눈" or eye == "Left Eye"):
                                next_test = True

                            elif len(result_list) == 2:
                                testEnd = True

                else:
                    counter = 0

                # ---------- 기본 화면 ----------
                draw_banner_with_text(
                    frame,
                    width,
                    height,
                    font,
                    guide_message
                )

                overlay_png(
                    frame,
                    20,
                    20,
                    btn_size // 4,
                    btn_size // 4,
                    logo
                )

                overlay_jpg(
                    frame,
                    img_test,
                    w2,
                    int(height * 0.40)
                )

                text_box(
                    frame,
                    int(width * 0.25),
                    int(height * 0.32),
                    "① ",
                    font,
                    (0, 0, 0)
                )

                text_box(
                    frame,
                    int(width * 0.43),
                    int(height * 0.32),
                    "② ",
                    font,
                    (0, 0, 0)
                )

                text_box(
                    frame,
                    int(width * 0.60),
                    int(height * 0.32),
                    "③ ",
                    font,
                    (0, 0, 0)
                )

                # 선택지 버튼 출력
                for btn in buttons:
                    overlay_png(
                        frame,
                        btn["pos"][0],
                        btn["pos"][1],
                        half,
                        half,
                        btn["img"]
                    )

                    if btn["val"] in selected_btns:
                        cv2.circle(
                            frame,
                            btn["pos"],
                            half + 3,
                            (0, 255, 0),
                            5,
                            cv2.LINE_AA
                        )

                # 현재 눈 표시
                overlay_png(
                    frame,
                    int(width * 0.13),
                    int(height * 0.82),
                    btn_size,
                    height // 15,
                    img_textbox
                )

                text_box(
                    frame,
                    int(btn_size * 0.75),
                    int(height * 0.8),
                    eye,
                    font,
                    (0, 0, 0)
                )

                # ---------- 결과 / 다음 테스트 ----------
                if testEnd:
                    should_break = overlay_test_result_screen(
                        frame,
                        background,
                        disease_name,
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

                elif next_test:
                    should_next = overlay_next_test_screen(
                        frame,
                        background,
                        timeStart,
                        height,
                        w2,
                        h2,
                        eye,
                        eyecarex_dir
                    )

                    if should_next:
                        next_test = False
                        eye = "왼쪽눈" if lang == "ko" else "Right Eye"
                        selected_btns = []
                        seq = []
                        counter = 0
                        timeStart = time.time()

                # ---------- 스트리밍 ----------
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