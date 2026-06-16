# project/eyecarex/eyetest/colortest/service_colortest.py
from flask import Blueprint, render_template, request, Response, current_app, url_for, redirect
from . import bp  # ← __init__.py의 bp를 가져옴 (중요)

@bp.get("/", endpoint="show")
def show():
    return render_template("colortest.html")

import cv2, time, datetime, os
from cvzone.FaceMeshModule import FaceMeshDetector
import mediapipe as mp
from PIL import ImageFont
from ...common.services import (
    overlay_png, overlay_jpg, text_box, save_results, 
    overlay_next_test_screen, overlay_test_result_screen, draw_banner_with_text
)

# ---------- 헬퍼 ----------
def hit(pt, center, half):  # (x,y) 버튼 히트 테스트
    return abs(pt[0]-center[0]) < half and abs(pt[1]-center[1]) < half

def decide_answer(seq3):
    a, b, btn = seq3
    if (a, b, btn) == (97, 74, 26):
        return '정상'
    if btn == 2:
        return '녹색맹'
    if btn == 6:
        return '적색맹'
    if b != 74 or btn != 26:
        return '적녹색맹'
    return '색각이상'

@bp.get("/cam")   # 최종 스트림 URL: /eyetest/colortest/cam
def cam():
    
    eyecarex_dir = current_app.blueprints['eyecarex'].static_folder
    curr_dir = bp.static_folder

    def gen():
        nowDatetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cap = cv2.VideoCapture(0)
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        w2, h2 = width//2, height//2

        btn_size  = width // 10
        half      = int(btn_size * 0.4)

        detector = FaceMeshDetector(maxFaces=1)
        hands = mp.solutions.hands.Hands(
            max_num_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5
        )

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

        # 문제 이미지(가로=화면 절반 기준 비율 유지 리사이즈)
        img_test = cv2.imread(os.path.join(curr_dir, "image", "colortest.jpg"))
        h_img, w_img, _ = img_test.shape
        img_test = cv2.resize(img_test, (w2, round(h_img * w2 / w_img)))

        # 선택지 아이콘(값/좌표/이미지) 5개를 한 곳에서 정의 os.path.join(curr_dir, "image", "2.png")
        buttons = [
            {'val': 2,  'pos': (int(width*0.30), int(height*0.70)), 'img': os.path.join(curr_dir, "image", "2.png")},
            {'val': 6,  'pos': (int(width*0.40), int(height*0.70)), 'img': os.path.join(curr_dir, "image", "6.png")},
            {'val': 26, 'pos': (int(width*0.50), int(height*0.70)), 'img': os.path.join(curr_dir, "image", "26.png")},
            {'val': 74, 'pos': (int(width*0.60), int(height*0.70)), 'img': os.path.join(curr_dir, "image", "74.png")},
            {'val': 97, 'pos': (int(width*0.70), int(height*0.70)), 'img': os.path.join(curr_dir, "image", "97.png")},
        ]

        # 상태 변수
        counter = 0
        seq = []
        selected_btns = []   # 선택된 버튼을 저장하는 리스트
        List = []
        answer = False
        next_test = False
        testEnd = False
        eye = '오른쪽눈'
        timeStart = time.time()
        disease_name = '색각'
        guide_message = ("제시된 그림 3개를 각각 보시고,\n"
                        "각 그림 속 숫자가 무엇인지 짚어주세요.")
        selectionSpeed = 8
        userID = "000000001"
        
        # ---------- 메인 루프 ----------
        while True:
            ok, frame = cap.read()
            if not ok: break

            # FaceMesh(BGR) + Hands(RGB) 처리 (RGB 왕복 1회)
            frame, _ = detector.findFaceMesh(frame, draw=False)
            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            if results.multi_hand_landmarks:
                H, W = frame.shape[:2]
                for hand in results.multi_hand_landmarks:
                    fx, fy = int(hand.landmark[8].x * W), int(hand.landmark[8].y * H)
                    cv2.circle(frame, (fx, fy), 5, (255, 0, 255), -1, cv2.LINE_AA)

                    # 모든 버튼을 하나의 루프에서 처리
                    hit_any = False
                    for btn in buttons:
                        if hit((fx, fy), btn['pos'], half):
                            hit_any = True
                            counter += 1
                            cv2.ellipse(frame, btn['pos'], (half, half), 0, 0, counter * selectionSpeed, (255,0,255), 10)
                            if counter * selectionSpeed == 360:
                                seq.append(btn['val'])
                                selected_btns.append(btn['val'])
                                timeStart = time.time()
                            break
                    if not hit_any:
                        counter = 0

                    # 3개 고르면 판정
                    if len(seq) == 3:
                        answer = decide_answer(tuple(seq))
                        seq.clear()
                        List = save_results(userID, nowDatetime, eye, answer, List, disease_name, eyecarex_dir)
                        timeStart = time.time()
                        if len(List) == 1 and eye == '오른쪽눈':
                            next_test = True
                        elif len(List) == 2:
                            testEnd = True

            # 상단 텍스트/문제/선택지/눈 표기
            draw_banner_with_text(frame, width, height, font, guide_message)        
            overlay_png(frame, *(20, 20), btn_size//4, btn_size//4, logo)
            
            overlay_jpg(frame, img_test, w2, int(height*0.40))
            text_box(frame, int(width*0.25), int(height*0.32), '① ', font, (0, 0, 0))
            text_box(frame, int(width*0.43), int(height*0.32), '② ', font, (0, 0, 0))
            text_box(frame, int(width*0.60), int(height*0.32), '③ ', font, (0, 0, 0))

            for btn in buttons:
                overlay_png(frame, *btn['pos'], half, half, cv2.imread(btn['img'], cv2.IMREAD_UNCHANGED))
                if btn['val'] in selected_btns:
                    cv2.circle(frame, btn['pos'], half+3, (0,255,0), 5, cv2.LINE_AA)

            overlay_png(frame, *(int(width*0.13), int(height*0.82)), btn_size, height//15, img_textbox)
            text_box(frame, int(btn_size*0.75), int(height*0.8), eye, font, (0, 0, 0))

            # 결과/다음 테스트 화면
            if testEnd:
                if overlay_test_result_screen(frame, background, disease_name, List, timeStart, height, w2, h2, font, eyecarex_dir):
                    break
            elif next_test:
                if overlay_next_test_screen(frame, background, timeStart, height, w2, h2, eye, eyecarex_dir):
                    next_test = False
                    eye = '왼쪽눈'
                    selected_btns = []

            # 인코딩 & 전송
            ok2, buf = cv2.imencode(".jpg", frame)
            if not ok2:
                continue
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

        cap.release()

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")
