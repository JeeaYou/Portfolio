# eyecarex/views/eyetest/comprehensive/service_comprehensive.py
from flask import Blueprint, render_template, request, Response, current_app, abort
from . import bp  # ← __init__.py의 bp를 가져옴 (중요)

TEMPLATES = {
    "astigmatism": "astigmatism.html",
    "glaucoma":    "glaucoma.html",
    "maculopathy": "maculopathy.html",
}

@bp.get("/<disease>", endpoint="show")
def show(disease):
    tpl = TEMPLATES.get(disease) or abort(404)
    return render_template(tpl, disease=disease)

import os, cv2, time, datetime
from cvzone.FaceMeshModule import FaceMeshDetector
import mediapipe as mp
from PIL import ImageFont
import numpy as np
from ...common.services import (
    overlay_png, overlay_jpg, text_box, save_results,
    overlay_next_test_screen, overlay_test_result_screen, draw_banner_with_text
)

TESTS = {
    "astigmatism": {"name": "난시", "img_rel": ("image", "astigmatism", "pikacyu.jpg"),
                    "window": "Astigmatism Test",
                    "guide": lambda ds, de: f"{ds}~{de}cm 거리에서 피카츄가 또렷하게 보이십니까?"},
    "glaucoma":    {"name": "녹내장", "img_rel": ("image", "glaucoma", "glaucoma.jpg"),
                    "window": "Glaucoma Test",
                    "guide": lambda ds, de: "이미지와 같은 자세로 정면을 바라보고 손이 보이나요?\n보이면 V, 보이지 않으면 X를 선택하세요."},
    "maculopathy": {"name": "황반변성", "img_rel": ("image", "maculopathy", "baduk.jpg"),
                    "window": "Macular degeneration Test",
                    "guide": lambda ds, de: "격자가 휘어지거나 일그러져 보이거나,\n중앙에 검은 점이 보이십니까?"},
}

@bp.get("/<disease>/cam", strict_slashes=False)
def cam(disease):
    cfg = TESTS.get(disease) or abort(404)
    
    d_start = 40
    d_end = 100
    
    # 핵심: 실제 파일이 있는 블루프린트의 static 디렉터리 기준으로!
    eyecarex_dir = current_app.blueprints['eyecarex'].static_folder
    static_dir = bp.static_folder

    img_path     = os.path.join(static_dir, *cfg["img_rel"])
    disease_name = cfg["name"]
    guide_message= cfg["guide"](d_start, d_end)

    def gen():
        nowDatetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cap = cv2.VideoCapture(0)
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))  or 1280
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
        w2, h2 = width//2, height//2

        btn_size = width // 10
        half     = btn_size // 2

        detector = FaceMeshDetector(maxFaces=1)
        hands = mp.solutions.hands.Hands(max_num_hands=1,
                                         min_detection_confidence=0.5,
                                         min_tracking_confidence=0.5)

        # 경로 만들기 + 검증해서 읽기
        font_path = os.path.join(eyecarex_dir, "fonts", "H2GSRB.TTF")
        bg_path   = os.path.join(eyecarex_dir, "image", "background.jpg")
        logo_path = os.path.join(eyecarex_dir, "button", "logo.png")
        tbx_path  = os.path.join(eyecarex_dir, "image", "textbox.png")
        
        # 리소스(파일 경로는 전부 static_dir 기준)
        font = ImageFont.truetype(font_path, 20)
        background  = cv2.resize(cv2.imread(bg_path,  cv2.IMREAD_COLOR), (width, height))
        logo        = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
        img_textbox = cv2.imread(tbx_path,  cv2.IMREAD_UNCHANGED)
        
        src = cv2.imread(img_path)
        if src is None:
            current_app.logger.error(f"[cam] image not found: {img_path}")
            # fallback: 빈 이미지라도 만들어서 크래시 방지
            src = 255 * np.ones((h2, w2, 3), dtype=np.uint8)
        img_test = cv2.resize(src, (w2, h2))


        btn_y  = int(height * 0.75)
        btnL_x = int(w2 * 0.75)
        btnR_x = int(w2 * 1.25)
        buttons = [
            {'val': disease_name, 'pos': (btnL_x, btn_y), 'img': os.path.join(eyecarex_dir, 'button', 'yes.png')},
            {'val': '정상',       'pos': (btnR_x, btn_y), 'img': os.path.join(eyecarex_dir, 'button', 'no.png')},
        ]

        counter   = 0
        List      = []
        testEnd   = False
        next_test = False
        eye       = '오른쪽눈'
        timeStart = time.time()
        selectionSpeed = 8
        userID = "000000001"

        def _hit(p, c, h): return abs(p[0]-c[0]) < h and abs(p[1]-c[1]) < h
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame, faces = detector.findFaceMesh(frame, draw=False)
            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            distance = None
            d_color  = (200,200,200)

            if faces:
                face = faces[0]
                pL, pR = face[145], face[374]
                w_pix, _ = detector.findDistance(pL, pR)
                W_cm, f_px = 6.3, 400
                distance = (W_cm * f_px) / w_pix

                if d_start < int(distance) <= d_end:
                    d_color = (255, 0, 255)
                    overlay_jpg(frame, img_test, w2, h2)

                    if results.multi_hand_landmarks:
                        fh, fw = frame.shape[:2]
                        for hand in results.multi_hand_landmarks:
                            fx = int(hand.landmark[8].x * fw)
                            fy = int(hand.landmark[8].y * fh)
                            cv2.circle(frame, (fx, fy), 5, (255, 0, 255), -1, cv2.LINE_AA)

                            hit_any = False
                            for btn in buttons:
                                if _hit((fx,fy), btn['pos'], half):
                                    hit_any = True
                                    counter += 1
                                    cv2.ellipse(frame, btn['pos'], (half, half), 0, 0,
                                                counter * selectionSpeed, (255,0,255), 10)
                                    if counter * selectionSpeed >= 360:  # >=로 안전하게
                                        answer = btn['val']
                                        timeStart = time.time()
                                        List = save_results(userID, nowDatetime, eye, answer, List, disease_name, eyecarex_dir)
                                        counter = 0
                                        if len(List) == 1 and eye == '오른쪽눈':
                                            next_test = True
                                        elif len(List) >= 2:
                                            testEnd = True
                                    break
                            if not hit_any:
                                counter = 0

            # 공통 UI
            draw_banner_with_text(frame, width, height, font, guide_message)
            overlay_png(frame, *(20,20), half//2, half//2, logo)

            txt = f' {int(distance)}cm ' if distance is not None else ' --cm '
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_PLAIN, 2, 2)
            cx = (width - tw)//2
            cy = height // 4
            cv2.rectangle(frame, (cx-8, cy-th-8), (cx+tw+8, cy+8), (0,0,0), -1)
            cv2.putText(frame, txt, (cx, cy), cv2.FONT_HERSHEY_PLAIN, 2, d_color, 2, cv2.LINE_AA)

            for btn in buttons:
                overlay_png(frame, *btn['pos'], half, half, cv2.imread(btn['img'], cv2.IMREAD_UNCHANGED))

            overlay_png(frame, *(int(width*0.13), int(height*0.82)), btn_size, height//15, img_textbox)
            text_box(frame, int(btn_size*0.75), int(height*0.8), eye, font, (0,0,0))

            if testEnd:
                if overlay_test_result_screen(frame, background, disease_name, List, timeStart, height, w2, h2, font, eyecarex_dir):
                    break
            elif next_test:
                if overlay_next_test_screen(frame, background, timeStart, height, w2, h2, eye, eyecarex_dir):
                    next_test = False
                    eye = '왼쪽눈'

            ok2, buf = cv2.imencode(".jpg", frame)
            if not ok2:
                continue
            yield (b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
        cap.release()

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")
