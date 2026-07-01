# project/eyecarex/eyetest/comprehensive/service_comprehensive.py

from flask import render_template, Response, current_app, abort
from . import bp

import os
import cv2
import time
import datetime
import numpy as np

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


TEMPLATES = {
    "astigmatism": "astigmatism.html",
    "glaucoma": "glaucoma.html",
    "maculopathy": "maculopathy.html",
}


TESTS = {
    "astigmatism": {
        "name": "난시" if lang == "ko" else "Astigmatism",
        "img_rel": ("image", "astigmatism", "pikacyu.jpg"),
        "window": "Astigmatism Test",
        "guide": lambda ds, de: f"{ds}~{de}cm 거리에서 피카츄가 또렷하게 보이십니까?" if lang == "ko" else f"Can you see Pikachu clearly at a distance of {ds}~{de}cm?"
    },
    "glaucoma": {
        "name": "녹내장" if lang == "ko" else "Glaucoma",
        "img_rel": ("image", "glaucoma", "glaucoma.jpg"),
        "window": "Glaucoma Test",
        "guide": lambda ds, de: "이미지와 같은 자세로 정면을 바라보고 손이 보이나요?\n보이면 V, 보이지 않으면 X를 선택하세요." if lang == "ko" else "Do you see your hand in the same position as the image?\nSelect V if you can see it, X if you cannot."
    },
    "maculopathy": {
        "name": "황반변성" if lang == "ko" else "Macular degeneration",
        "img_rel": ("image", "maculopathy", "baduk.jpg"),
        "window": "Macular degeneration Test",
        "guide": lambda ds, de: "격자가 휘어지거나 일그러져 보이거나,\n중앙에 검은 점이 보이십니까?" if lang == "ko" else "Do you see the grid distorted or warped,\nor a black dot in the center?"
    },
}


@bp.get("/<disease>", endpoint="show")
def show(disease):
    tpl = TEMPLATES.get(disease) or abort(404)
    return render_template(tpl, disease=disease, lang=lang)


def read_image(path, flag=cv2.IMREAD_UNCHANGED, name="이미지"):
    img = cv2.imread(path, flag)

    if img is None:
        raise FileNotFoundError(f"{name}를 읽을 수 없습니다: {path}")

    return img


def hit(point, center, half):
    return abs(point[0] - center[0]) < half and abs(point[1] - center[1]) < half


@bp.get("/<disease>/cam", strict_slashes=False)
def cam(disease):
    cfg = TESTS.get(disease) or abort(404)

    d_start = 40
    d_end = 100

    # project/eyecarex/static
    eyecarex_dir = current_app.blueprints["eyecarex"].static_folder

    # project/eyecarex/eyetest/comprehensive/static
    static_dir = bp.static_folder

    img_path = os.path.join(static_dir, *cfg["img_rel"])
    disease_name = cfg["name"]
    guide_message = cfg["guide"](d_start, d_end)

    def gen():
        nowDatetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            raise RuntimeError("Can't open camera.")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720

        w2, h2 = width // 2, height // 2

        btn_size = width // 10
        half = btn_size // 2

        # 기존 mediapipe 직접 사용 제거
        detector = FaceMeshDetector(maxFaces=1)
        hand_detector = HandDetector(maxHands=1, detectionCon=0.5)

        # ---------- 경로 ----------
        font_path = os.path.join(eyecarex_dir, "fonts", "H2GSRB.TTF")
        bg_path = os.path.join(eyecarex_dir, "image", "background.jpg")

        # 기존 button/logo.png 아님
        # project/eyecarex/static/image/logo.png 기준
        logo_path = os.path.join(eyecarex_dir, "image", "logo.png")

        tbx_path = os.path.join(eyecarex_dir, "image", "textbox.png")

        yes_path = os.path.join(eyecarex_dir, "button", "yes.png")
        no_path = os.path.join(eyecarex_dir, "button", "no.png")

        # ---------- 리소스 ----------
        if not os.path.exists(font_path):
            raise FileNotFoundError(f"Font file not found: {font_path}")

        font = ImageFont.truetype(font_path, 20)

        background_raw = read_image(bg_path, cv2.IMREAD_COLOR, "background 이미지")
        logo = read_image(logo_path, cv2.IMREAD_UNCHANGED, "logo 이미지")
        img_textbox = read_image(tbx_path, cv2.IMREAD_UNCHANGED, "textbox 이미지")

        yes_img = read_image(yes_path, cv2.IMREAD_UNCHANGED, "yes 버튼 이미지")
        no_img = read_image(no_path, cv2.IMREAD_UNCHANGED, "no 버튼 이미지")

        background = cv2.resize(background_raw, (width, height))

        src = cv2.imread(img_path)

        if src is None:
            current_app.logger.error(f"[cam] image not found: {img_path}")
            src = 255 * np.ones((h2, w2, 3), dtype=np.uint8)

        img_test = cv2.resize(src, (w2, h2))

        # ---------- 버튼 ----------
        btn_y = int(height * 0.75)
        btnL_x = int(w2 * 0.75)
        btnR_x = int(w2 * 1.25)

        buttons = [
            {
                "val": disease_name,
                "pos": (btnL_x, btn_y),
                "img": yes_img
            },
            {
                "val": "정상" if lang == "ko" else "Normal",
                "pos": (btnR_x, btn_y),
                "img": no_img
            },
        ]

        # ---------- 상태 ----------
        counter = 0
        result_list = []

        testEnd = False
        next_test = False

        eye = "오른쪽눈" if lang == "ko" else "Left eye"
        timeStart = time.time()

        selectionSpeed = 8
        userID = "000000001"

        try:
            while True:
                ok, frame = cap.read()

                if not ok:
                    break
                frame = cv2.flip(frame, 1)
                frame, faces = detector.findFaceMesh(frame, draw=False)

                hands, frame = hand_detector.findHands(
                    frame,
                    draw=False,
                    flipType=False
                )

                distance = None
                d_color = (200, 200, 200)

                if faces:
                    face = faces[0]

                    try:
                        pL = face[145]
                        pR = face[374]

                        w_pix, _ = detector.findDistance(pL, pR)

                        if w_pix and w_pix > 0:
                            W_cm = 6.3
                            f_px = 400
                            distance = (W_cm * f_px) / w_pix

                    except Exception:
                        distance = None

                    if distance is not None and d_start < int(distance) <= d_end:
                        d_color = (255, 0, 255)

                        overlay_jpg(
                            frame,
                            img_test,
                            w2,
                            h2
                        )

                        if hands:
                            hand = hands[0]
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
                                            answer = btn["val"]
                                            timeStart = time.time()

                                            result_list = save_results(
                                                userID,
                                                nowDatetime,
                                                eye,
                                                answer,
                                                result_list,
                                                disease_name,
                                                eyecarex_dir
                                            )

                                            counter = 0

                                            if len(result_list) == 1 and (eye == "오른쪽눈" or eye == "Left eye"):
                                                next_test = True

                                            elif len(result_list) >= 2:
                                                testEnd = True

                                        break

                                if not hit_any:
                                    counter = 0

                        else:
                            counter = 0

                else:
                    counter = 0

                # ---------- 공통 UI ----------
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
                    half // 2,
                    half // 2,
                    logo
                )

                if distance is not None:
                    txt = f" {int(distance)}cm "
                else:
                    txt = " --cm "

                (tw, th), _ = cv2.getTextSize(
                    txt,
                    cv2.FONT_HERSHEY_PLAIN,
                    2,
                    2
                )

                cx = (width - tw) // 2
                cy = height // 4

                cv2.rectangle(
                    frame,
                    (cx - 8, cy - th - 8),
                    (cx + tw + 8, cy + 8),
                    (0, 0, 0),
                    -1
                )

                cv2.putText(
                    frame,
                    txt,
                    (cx, cy),
                    cv2.FONT_HERSHEY_PLAIN,
                    2,
                    d_color,
                    2,
                    cv2.LINE_AA
                )

                for btn in buttons:
                    overlay_png(
                        frame,
                        btn["pos"][0],
                        btn["pos"][1],
                        half,
                        half,
                        btn["img"]
                    )

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
                        eye = "왼쪽눈" if lang == "ko" else "Right eye"
                        counter = 0
                        timeStart = time.time()

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