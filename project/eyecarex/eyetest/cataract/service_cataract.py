
# project/eyecarex/eyetest/cataract/service_cataract.py
from flask import Blueprint, render_template, request, Response, current_app, url_for, redirect
from . import bp  # ← __init__.py의 bp를 가져옴 (중요)
@bp.get("/", endpoint="show")
def show():
    return render_template("cataract.html")

import cv2, time, datetime, os
from cvzone.FaceMeshModule import FaceMeshDetector
import mediapipe as mp
from PIL import ImageFont
import pandas as pd
import shutil
from ...common.services import (
    overlay_png, overlay_jpg, text_box, save_results, 
    overlay_next_test_screen, overlay_test_result_screen, draw_banner_with_text
)
from .static.models.cataract_predict import image_test

@bp.get("/cam")   # 최종 스트림 URL: /eyetest/colortest/cam
def cam():
    eyecarex_dir = current_app.blueprints['eyecarex'].static_folder
    curr_dir = bp.static_folder

    def gen():
        image_dir = os.path.join(curr_dir, "image")
        if os.path.exists(image_dir):
            shutil.rmtree(image_dir)   # 폴더 전체 삭제
        os.makedirs(image_dir, exist_ok=True)  # 새로 생성
            
        cap = cv2.VideoCapture(0)
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        w2, h2 = width//2, height//2

        btn_size  = width // 10
        half      = int(btn_size * 0.4)

        detector = FaceMeshDetector(maxFaces=1)
        face = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        hands = mp.solutions.hands.Hands(
            max_num_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5
        )
        
        # 경로 만들기 + 검증해서 읽기
        font_path = os.path.join(eyecarex_dir, "fonts", "H2GSRB.TTF")
        bg_path   = os.path.join(eyecarex_dir, "image", "background.jpg")
        logo_path = os.path.join(eyecarex_dir, "button", "logo.png")
        face_path = os.path.join(eyecarex_dir, "button", "face.png")
        
        # 리소스(파일 경로는 전부 static_dir 기준)
        font = ImageFont.truetype(font_path, 20)
        background  = cv2.resize(cv2.imread(bg_path,  cv2.IMREAD_COLOR), (width, height))
        logo        = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
        face_img    = cv2.imread(face_path, cv2.IMREAD_UNCHANGED)

        name = '백내장'
        List = []
        timeStart = time.time()
        testEnd = False
        captured = False  # ← 한 번만 캡쳐하기 위한 플래그

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            
            frame, faces = detector.findFaceMesh(frame, draw=False)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # ✅ 각각 따로 처리
            face_res  = face.process(rgb)    # 얼굴(eye keypoints: detections)
            hands_res = hands.process(rgb)       # 손(landmarks)

            if face_res.detections:
                det = face_res.detections[0]
                kps = det.location_data.relative_keypoints
                # kps[0]=right eye, kps[1]=left eye (미디어파이프 정의)
                r_eye = kps[0]
                l_eye = kps[1]

                h, w, _ = frame.shape
                rx1 = max(int(r_eye.x * w - 60), 0); ry1 = max(int(r_eye.y * h - 40), 0)
                rx2 = min(int(r_eye.x * w + 40), w);  ry2 = min(int(r_eye.y * h + 40), h)
                lx1 = max(int(l_eye.x * w - 40), 0);  ly1 = max(int(l_eye.y * h - 40), 0)
                lx2 = min(int(l_eye.x * w + 40), w);  ly2 = min(int(l_eye.y * h + 40), h)

                right = frame[ry1:ry2, rx1:rx2]
                left  = frame[ly1:ly2, lx1:lx2]

                now = datetime.datetime.now().strftime("%d_%H-%M-%S")
                right_name = os.path.join(curr_dir, "image", 'right_image' + str(now) + ".jpg")
                left_name = os.path.join(curr_dir, "image", 'left_image' + str(now) + ".jpg")

                overlay_png(frame, *(w2,h2), int(h2//2), int(h2//2), face_img)

                if hands_res.multi_hand_landmarks:
                    for hand_landmarks in hands_res.multi_hand_landmarks:
                        finger1 = int(hand_landmarks.landmark[8].y * 100)
                        finger2 = int(hand_landmarks.landmark[5].y * 100)
                        hand_y  = int(hand_landmarks.landmark[0].y * 100)
                        dist = abs(finger1 - hand_y)
                        dist2 = abs(finger2 - hand_y)

                        if dist == dist2 and captured is False:
                            cv2.imwrite(left_name, left)
                            class_name, score = image_test(left_name)
                            score_str = str(score) + '%'
                            List.append({
                                        '눈':'오른쪽눈',
                                        '여부': class_name,
                                        '확률': score_str,
                                        '이미지': right_name
                                    })
                            cv2.imwrite(right_name, right)
                            class_name, score = image_test(right_name)
                            score_str = str(score) + '%'
                            List.append({
                                        '눈':'왼쪽눈',
                                        '여부': class_name,
                                        '확률': score_str,
                                        '이미지': right_name
                                    })
                            df = pd.DataFrame(List)
                            df.to_csv(eyecarex_dir + f'/csv_file/{name}.csv')
                            captured = True
                            testEnd = True                
                            
            # 공통 UI            
            draw_banner_with_text(frame, width, height, font, '카메라를 보고 손을 펼친 뒤, 주먹을 쥐면 촬영됩니다.')
            overlay_png(frame, *(20, 20), half//2, half//2, logo)

            if testEnd:
                # 결과 화면까지 프레임에 그려서 보여주고 루프 종료
                if overlay_test_result_screen(frame, background, name, List, timeStart, height, w2, h2, font, eyecarex_dir):
                    List = []
                    pass
                
            # 인코딩 & 전송
            ok2, buf = cv2.imencode(".jpg", frame)
            if not ok2:
                continue
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

        cap.release()


    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


