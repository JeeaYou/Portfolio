# eyecarex/views/game/service_game.py
from flask import render_template,  Response, current_app
from . import bp  # ← __init__.py의 bp를 가져옴 (중요)

@bp.get("/", endpoint="show")
def show():
    return render_template("winkbird.html")

import os, cv2, time, datetime, random
import numpy as np
import mediapipe as mp
import pandas as pd
import cvzone
from cvzone.FaceMeshModule import FaceMeshDetector
from PIL import ImageFont
# 공용 유틸 (당신 프로젝트 경로에 맞게)
from ...common.services import (
    overlay_png, overlay_jpg, text_box, draw_banner_with_text
)

@bp.get("/cam")
def cam():
    eyecarex_dir = current_app.blueprints['eyecarex'].static_folder
    game_dir = current_app.blueprints['eyecarex.game'].static_folder
    curr_dir = bp.static_folder

    static_dir = current_app.static_folder
    nowDatetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def gen():
        cap = cv2.VideoCapture(0)
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        w2, h2 = width // 2, height // 2
        btn_size = width // 10

        detector = FaceMeshDetector(maxFaces=1)
        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.5, min_tracking_confidence=0.5)

        # 리소스 경로
        font_path = os.path.join(eyecarex_dir, "fonts", "H2GSRB.TTF")
        font_small  = ImageFont.truetype(font_path, 20)
        font_big    = ImageFont.truetype(font_path, max(24, width // 5))
        font_timer  = ImageFont.truetype(font_path, h2 // 8)
        font_gameov = ImageFont.truetype(font_path, height // 10)
        
        bg_path   = os.path.join(eyecarex_dir, "image", "background.jpg")
        logo_path = os.path.join(eyecarex_dir, "button", "logo.png")
        tbx_path  = os.path.join(eyecarex_dir, "image", "textbox.png")
        left_path = os.path.join(game_dir, "image", "start.png")
        
        # 리소스(파일 경로는 전부 static_dir 기준)
        background  = cv2.resize(cv2.imread(bg_path,  cv2.IMREAD_COLOR), (width, height))
        logo        = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
        textbox_img = cv2.imread(tbx_path,  cv2.IMREAD_UNCHANGED)
        start_img        = cv2.imread(left_path, cv2.IMREAD_UNCHANGED)

        # 게임 오브젝트 로딩
        bird_dir = os.path.join(curr_dir, 'image')
        files = [f for f in (os.listdir(bird_dir) if os.path.isdir(bird_dir) else []) if f.lower().endswith(('.png', '.webp'))]
        catch = []
        for fname in files:
            catch.append(cv2.resize(cv2.imread(os.path.join(bird_dir, fname), cv2.IMREAD_UNCHANGED), (btn_size, btn_size)))
        if not catch:
            # 최소 1개 생성 (없어도 게임 깨지지 않도록)
            catch = [255 * np.ones((btn_size, btn_size, 4), dtype=np.uint8)]

        current_obj = catch[0]
        pos = [random.randint(0, max(0, width - btn_size)), 0]
        speed = 5
        count = 0

        # 상태 변수들
        press_start = None
        HOLD_SEC = 2.0
        started = False
        counting_down = False
        countdown_end = None
        timeStart = None
        endTime = None
        gameOver = False
        totalTime = 30

        # 눈 깜빡임 판정
        eye_dist_close, eye_dist_open = 33, 37
        blink_in_progress = False
        closed_frames = 0
        cooldown = 0
        CLOSE_MIN_FRAMES = 2
        ratioList = []
        userID = "000000001"
        guide = f"{totalTime}초 동안 깜빡임으로 새를 잡아보세요."

        def reset_object():
            pos[0] = random.randint(0, max(0, width - btn_size))
            pos[1] = 0
            return catch[random.randrange(len(catch))]

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            # --- 아직 시작 전 ---
            if not started and not counting_down:
                draw_banner_with_text(frame, width, height, font_small, 'START 버튼에 2초간 터치하세요.')
                overlay_png(frame, *(20, 20), btn_size//4, btn_size//4, logo)

                half_w, half_h = width//5, height//5
                overlay_png(frame, *(w2, h2), half_w, half_h, start_img)
                start_btn = (w2 - half_w, h2 - half_h, w2 + half_w, h2 + half_h)

                results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

                touching = False
                if results.multi_hand_landmarks:
                    H, W = frame.shape[:2]
                    for hand in results.multi_hand_landmarks:
                        fx, fy = int(hand.landmark[8].x * W), int(hand.landmark[8].y * H)
                        if (start_btn[0] <= fx <= start_btn[2]) and (start_btn[1] <= fy <= start_btn[3]):
                            touching = True
                            break

                if touching:
                    if press_start is None:
                        press_start = time.time()
                    held = time.time() - press_start
                    progress = min(360, int(360 * (held / HOLD_SEC)))
                    cv2.ellipse(frame, (w2, h2), (half_w, half_h), 0, 0, progress, (255, 0, 255), 8)
                    if held >= HOLD_SEC:
                        counting_down = True
                        countdown_end = time.time() + 5.0
                        press_start = None
                else:
                    press_start = None

            # --- 카운트다운 ---
            elif counting_down and not started:
                draw_banner_with_text(frame, width, height, font_small, guide)
                overlay_png(frame, *(20, 20), btn_size//4, btn_size//4, logo)

                remain = countdown_end - time.time()
                if remain > 0:
                    sec = int(remain) + 1
                    text_box(frame, None, None, "GO!" if sec <= 0 else str(sec), font_big, (255, 0, 255))
                else:
                    started = True
                    timeStart = time.time()
                    endTime = timeStart + float(totalTime)
                    counting_down = False

            # --- 게임 진행 ---
            elif not gameOver:
                draw_banner_with_text(frame, width, height, font_small, guide)
                overlay_png(frame, *(20, 20), btn_size//4, btn_size//4, logo)

                remaining = int(endTime - time.time())
                gameOn = remaining >= 0

                if gameOn:
                    frame, faces = detector.findFaceMesh(frame, draw=False)

                    # 오브젝트 이동
                    pos[1] += speed
                    if pos[1] > height - btn_size:
                        current_obj = reset_object()
                    else:
                        if 0 <= pos[0] <= width - btn_size and 0 <= pos[1] <= height - btn_size:
                            frame = cvzone.overlayPNG(frame, current_obj, pos)
                        else:
                            current_obj = reset_object()

                    # 얼굴/깜빡임
                    if faces:
                        face = faces[0]
                        up, down = face[159], face[23]
                        left, right = face[130], face[243]
                        upDown, _ = detector.findDistance(up, down)
                        leftRight, _ = detector.findDistance(left, right)
                        ratio = int((upDown / leftRight) * 100) if leftRight else 999

                        ratioList.append(ratio)
                        if len(ratioList) > 3: ratioList.pop(0)
                        ratioAvg = sum(ratioList) / len(ratioList)

                        closed_frames = closed_frames + 1 if ratioAvg < eye_dist_close else 0
                        if cooldown > 0: cooldown -= 1

                        # 깜빡임 시작
                        if (not blink_in_progress) and (closed_frames >= CLOSE_MIN_FRAMES) and (cooldown == 0):
                            blink_in_progress = True
                        # 깜빡임 끝 (다시 열림)
                        elif blink_in_progress and (ratioAvg > eye_dist_open):
                            current_obj = reset_object()
                            count += 1
                            blink_in_progress = False
                            cooldown = 6

                    # 하단 UI
                    overlay_png(frame, *(int(width*0.16), int(height*0.82)), width // 7, height//15, textbox_img)
                    text_box(frame, int(btn_size*0.75), int(height*0.8), f'Score: {count}', font_small, (0, 0, 0))
                    text_box(frame, width - 150, 20, f'Time: {remaining}', font_timer, (255, 0, 255))
                else:                        
                    gameOver = True

            # --- 게임오버 ---
            else:
                overlay_jpg(frame, background, w2, h2)
                text_box(frame, None, int(height * 0.35), "Game Over", font_gameov, (0, 0, 0))
                text_box(frame, None, int(height * 0.60), f'Your Score: {count}', font_small, (0, 0, 0))
                text_box(frame, None, int(height * 0.72), f'게임 다시 시작할려면 다시하기 누르시오.', font_gameov, (0, 0, 0))
                
                csv_dir = os.path.join(eyecarex_dir, 'csv_file')
                os.makedirs(csv_dir, exist_ok=True)
                csv_path = os.path.join(csv_dir, '게임.csv')
                row = {'ID': userID, '시간': nowDatetime, '점수': str(count)}
                df = pd.DataFrame([row])
                if os.path.exists(csv_path):
                    df.to_csv(csv_path, mode='a', index=False, header=False, encoding='utf-8-sig')
                else:
                    df.to_csv(csv_path, index=False, encoding='utf-8-sig')

            # 스트림 전송
            ok2, buf = cv2.imencode(".jpg", frame)
            if not ok2: 
                continue
            yield (b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

            # cap.release()
            # 점수 저장

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")
