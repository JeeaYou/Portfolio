# project/eyecarex/eyetest/eyevision/service_eyevision.py
from flask import Blueprint, render_template, Response, current_app, url_for, redirect
from . import bp  # ← __init__.py의 bp를 가져옴 (중요)
import os, cv2, time, datetime
import urllib.request

from cvzone.FaceMeshModule import FaceMeshDetector
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from PIL import ImageFont

# 공용/eyevision 모듈들
from ...common.services import (
    get_lang, load_texts, overlay_png, overlay_jpg, text_box, save_results,
    overlay_next_test_screen, overlay_test_result_screen, draw_banner_with_text
)
from .eyeVision_Module import (
    make_eyeChart, get_eyeImg, answer_true_false, load_next_image, result_checking
)

@bp.get("/", endpoint="show")  # 최종 이름: eyetest.eyevision.show
def show():
    
    lang = get_lang()

    return render_template("eyevision.html",
                           lang = lang)


def hit(p, center, half):
    x, y = p; cx, cy = center
    return abs(x - cx) < half and abs(y - cy) < half

def ensure_hand_landmarker_model(eyecarex_dir):
    model_dir = os.path.join(eyecarex_dir, "models")
    os.makedirs(model_dir, exist_ok=True)

    model_path = os.path.join(model_dir, "hand_landmarker.task")

    if not os.path.exists(model_path):
        print("Downloading MediaPipe HandLandmarker model...")

        model_url = (
            "https://storage.googleapis.com/mediapipe-models/"
            "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
        )

        urllib.request.urlretrieve(model_url, model_path)
        print("HandLandmarker download complete.")

    return model_path

@bp.get("/cam")   # 최종 스트림 URL: /eyetest/eyevision/cam
def cam():

    lang = get_lang()

    eyecarex_dir = current_app.blueprints['eyecarex'].static_folder
    curr_dir = bp.static_folder
    
    def gen():
        nowDatetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cap = cv2.VideoCapture(0)
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))  or 1280
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
        w2, h2 = width//2, height//2
        btn_size  = width//10
        half      = btn_size//2

        detector = FaceMeshDetector(maxFaces=1)

        hand_model_path = ensure_hand_landmarker_model(eyecarex_dir)

        hand_options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=hand_model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        hand_landmarker = vision.HandLandmarker.create_from_options(hand_options)
        
        # 2) 경로 만들기 + 검증해서 읽기
        font_path = os.path.join(eyecarex_dir, "fonts", "H2GSRB.TTF")
        bg_path   = os.path.join(eyecarex_dir, "image", "background.jpg")
        logo_path = os.path.join(eyecarex_dir, "image", "logo.png")
        tbx_path  = os.path.join(eyecarex_dir, "image", "textbox.png")
        left_path = os.path.join(eyecarex_dir, "button", "left.png")
        
        # 리소스(파일 경로는 전부 static_dir 기준)
        font = ImageFont.truetype(font_path, 40)
        background  = cv2.resize(cv2.imread(bg_path,  cv2.IMREAD_COLOR), (width, height))
        logo        = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
        img_textbox = cv2.imread(tbx_path,  cv2.IMREAD_UNCHANGED)
        base        = cv2.imread(left_path, cv2.IMREAD_UNCHANGED)
        icons = {
            'left' : base,
            'right': cv2.rotate(base, cv2.ROTATE_180),
            'up'   : cv2.rotate(base, cv2.ROTATE_90_CLOCKWISE),
            'down' : cv2.rotate(base, cv2.ROTATE_90_COUNTERCLOCKWISE),
        }
        buttons = [
            ('left',  (int(width * 0.30), int(h2 * 1.15))),
            ('right', (int(width * 0.70), int(h2 * 1.15))),
            ('up',    (w2, int(height * 0.30))),
            ('down',  (w2, int(height * 0.83))),
        ]

        # 시력도표/상태
        dataList = make_eyeChart(curr_dir)
        level, max_level = int(dataList['level'].min()), int(dataList['level'].max())
        answer_list, test_count, wrong_cnt = [], 0, 0
        mode, finish, next_test, testEnd = 'normal', False, False, False
        eye = '오른쪽눈' if lang is 'ko'  else 'Left Eye'
        img_name, img_level, img_eyelevel, img_url = get_eyeImg(level, dataList)
        img_raw = cv2.imread(img_url)

        if img_raw is None:
            raise FileNotFoundError(f"Can't read image file : {img_url}")

        img_test = cv2.resize(img_raw, (h2, h2))
        
        List = []

        counter = 0
        timeStart = time.time()
        distance, d_color = 0, (200,200,200)
        
        d_start = 0
        d_end = 40
        selectionSpeed = 8
        userID = "000000001"
        max_test_count = 15
        name = '시력' if lang == 'ko'  else 'Visual Acuity'
        print(lang)
        dict_text = (
            f"{d_start}~{d_end}cm 거리에서 보이는 글자의 방향은 어디인가요?"
            if lang == "ko"
            else f"Which direction is the letter facing at a distance of {d_start}~{d_end} cm?"
        )

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame = cv2.flip(frame, 1)
            frame, faces = detector.findFaceMesh(frame, draw=False)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame
            )
            hand_results = hand_landmarker.detect(mp_image)

            if faces:
                face = faces[0]
                pointLeft, pointRight = face[145], face[374]
                w_dist, _ = detector.findDistance(pointLeft, pointRight)
                W, fz = 6.3, 400
                distance = (W * fz) / w_dist if w_dist else 999
                in_range = d_start < int(distance) <= d_end
                d_color = (255, 0, 255) if in_range else (200, 200, 200)

                if in_range:
                    overlay_jpg(frame, img_test, w2, int(h2 * 1.15))
                    if hand_results.hand_landmarks:
                        h_img, w_img = frame.shape[:2]

                        for hand in hand_results.hand_landmarks:
                            index_finger_tip = hand[8]

                            fx = int(index_finger_tip.x * w_img)
                            fy = int(index_finger_tip.y * h_img)
                            cv2.circle(frame, (fx, fy), 5, (255, 0, 255), -1, cv2.LINE_AA)

                            hit_any = False
                            for label, center in buttons:
                                if hit((fx, fy), center, half):
                                    hit_any = True
                                    counter += 1
                                    cv2.ellipse(frame, center, (half, half), 0, 0,
                                                counter * selectionSpeed, (255,0,255), 10)
                                    if counter * selectionSpeed >= 360:
                                        answer, level, mode, wrong_cnt, answer_list, test_count, finish = \
                                            answer_true_false(label, img_name, img_eyelevel, img_level,
                                                              answer_list, mode, level, wrong_cnt,
                                                              max_level, test_count, max_test_count)
                                        timeStart = time.time()
                                        img_name, img_level, img_eyelevel, img_url, img_test = \
                                            load_next_image(level, dataList, h2, h2)
                                        counter = 0
                                    break
                            if not hit_any:
                                counter = 0

                            if finish:
                                level = 1
                                answer = result_checking(answer_list)
                                finish = False
                                List = save_results(userID, nowDatetime, eye, answer, List, name, eyecarex_dir)
                                timeStart = time.time()
                                next_test = (len(List) == 1)
                                testEnd   = (len(List) == 2)

            # 공통 UI
            txt = f' {int(distance)}cm ' if distance is not None else ' --cm '
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_PLAIN, 2, 2)
            cx = (width - tw)//2
            cy = height // 5
            cv2.rectangle(frame, (cx-8, cy-th-8), (cx+tw+8, cy+8), (0,0,0), -1)
            cv2.putText(frame, txt, (cx, cy), cv2.FONT_HERSHEY_PLAIN, 2, d_color, 2, cv2.LINE_AA)

            draw_banner_with_text(frame, width, height, font, dict_text)
            overlay_png(frame, *(60, 60), half//2, half//2, logo)

            for label, center in buttons:
                overlay_png(frame, *center, half, half, icons[label])

            overlay_png(frame, *(int(width*0.13), int(height*0.82)), btn_size, height//15, img_textbox)
            text_box(frame, int(btn_size*0.75), int(height*0.8), eye, font, (0, 0, 0))

            if testEnd and len(List) == 2:
                # 결과 화면까지 프레임에 그려서 보여주고 루프 종료
                if overlay_test_result_screen(frame, background, name, List, timeStart, height, w2, h2, font, eyecarex_dir):
                    pass
            elif next_test:
                if overlay_next_test_screen(frame, background, timeStart, height, w2, h2, eye, eyecarex_dir):
                    next_test = False
                    eye = '왼쪽눈' if lang is 'ko'  else 'Right Eye'
                    level, wrong_cnt, test_count, mode, counter = 1, 0, 0, 'normal', 0
                    answer_list = []
                    img_name, img_level, img_eyelevel, img_url, img_test = \
                        load_next_image(level, dataList, h2, h2)

            # 인코딩 & 전송
            ok2, buf = cv2.imencode(".jpg", frame)
            if not ok2:
                continue
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

        hand_landmarker.close()
        cap.release()

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")
