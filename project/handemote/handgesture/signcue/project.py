# 라이브러리 
from operator import methodcaller
from flask import Flask, render_template, request, Response
#library import
import cv2
import mediapipe as mp
import numpy as np
from tensorflow.keras.models import load_model
from multiprocessing import Process ,Queue
import time

app = Flask(__name__)


#액션 구분 및 행동 길이 설정
actions =  ['best','ok','yeah','heart']
seq_length = 30

#학습모델 로드
model = load_model('static/model.h5')

# MediaPipe hands model
mp_hands = mp.solutions.hands
mp_pose = mp.solutions.pose

hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5)

def overlay(img, x, y, w, h, overlay_image): # 대상 이미지 (3채널), x, y 좌표, width, height, 덮어씌울 이미지 (4채널:투명도를 가짐)
    alpha = overlay_image[:, :, 3]   # BGR
    image_alpha = alpha/ 255  # 0 ~ 255 -> 255 로 나누면 0 ~ 1 사이의 값 (1: 불투명, 0: 완전투명)
    for c in range(3): # channel BGR
        img[y-h:y+h, x-w:x+w, c] = (overlay_image[:, :, c] * image_alpha) + (img[y-h:y+h, x-w:x+w, c] * (1 - image_alpha))

cap = cv2.VideoCapture(0)

#캠 너비 및 높이 로드
width_cam = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
height_cam = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

img_size = 40

#sequence 및 action 저장할 리스트 생성
seq = []
action_seq = []

#캐릭터 이미지 로드
img_good = cv2.resize(cv2.imread('static/icon/good-job.png',-1),(80,80))
img_ok = cv2.resize(cv2.imread('static/icon/ok.png',-1),(80,80))
img_lovely = cv2.resize(cv2.imread('static/icon/lovely.png',-1),(80,80))
img_heart = cv2.resize(cv2.imread('static/icon/heart.png',-1),(80,80))

# 시간 및 카운터 설정

cap = cv2.VideoCapture(0)

# 메인 서버
@app.route("/")
def hello_world():
    return render_template("main.html")

# 이미지 페이지 서버
@app.route("/image_page")
def first():
    return render_template("image_page.html")

# 메인카메라 서버
@app.route("/Camera")
def camera():
    return render_template("camera.html")

def gen(cap):
# 시간 및 카운터 설정
    start_time = time.time()
    text_counter = 0

    while cap.isOpened():
        ret, img = cap.read()
        img0 = img.copy()

        img = cv2.flip(img, 1)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        result = hands.process(img)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        if time.time() - start_time > 2:
            start_time = time.time()
        
        cv2.putText(img, f'best, ok, yeah, heart'.upper(), org=(120,50),  fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=1, color=(255, 255, 255), thickness=2)
        if result.multi_hand_landmarks is not None:
            for res in result.multi_hand_landmarks:
                finger = res.landmark[8]
                h, w, _=img.shape 
                x_finger, y_finger=int(finger.x*w), int(finger.y*h)
                joint = np.zeros((21, 4))
                for j, lm in enumerate(res.landmark):
                    joint[j] = [lm.x, lm.y, lm.z, lm.visibility]

                # Compute angles between joints
                v1 = joint[[0,1,2,3,0,5,6,7,0,9,10,11,0,13,14,15,0,17,18,19], :3] # Parent joint
                v2 = joint[[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20], :3] # Child joint
                v = v2 - v1 # [20, 3]
                # Normalize v
                v = v / np.linalg.norm(v, axis=1)[:, np.newaxis]
                # Get angle using arcos of dot product
                angle = np.arccos(np.einsum('nt,nt->n',
                    v[[0,1,2,4,5,6,8,9,10,12,13,14,16,17,18],:], 
                    v[[1,2,3,5,6,7,9,10,11,13,14,15,17,18,19],:])) # [15,]

                angle = np.degrees(angle) # Convert radian to degree
                # angle = np.append(angle,dist)
                d = np.concatenate([joint.flatten(), angle])

                seq.append(d)

                if len(seq) < seq_length:
                    continue
                
                input_data = np.expand_dims(np.array(seq[-seq_length:], dtype=np.float32), axis=0)

                y_pred = model.predict(input_data).squeeze()
                #학습모델 불러 맞는지 확인
                i_pred = int(np.argmax(y_pred))
                conf = y_pred[i_pred]
                #확률 90% 이상 일 때 action값 보여줌
                if conf < 0.9:
                    continue
                action = actions[i_pred]
                action_seq.append(action)
                #행동값이 적으면 일단 실행
                if len(action_seq) < 3:
                    continue
                #행동을 프레임으로 구분 - 마지막, 그 전, 그 전전이 같은 행동이면 교체
                this_action = '?'
                if action_seq[-1] == action_seq[-2] == action_seq[-3]:
                    this_action = action
                    #현재 행동이 무엇인가에 따라 실행 확대/축소
                    if this_action == actions[0]:        
                        overlay(img, x_finger+120, y_finger-50, img_size, img_size, img_good)
        
                    elif this_action == actions[1]:
                        overlay(img, x_finger+150, y_finger, img_size, img_size, img_ok)
                        
                    elif this_action == actions[2]:
                        overlay(img, x_finger, y_finger-50, img_size, img_size, img_lovely)

                    elif this_action == actions[3]:
                        overlay(img, x_finger, y_finger-50, img_size, img_size, img_heart)
                                
                cv2.putText(img, f'{this_action.upper()}', org=(220, 450), fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=1, color=(255, 255, 255), thickness=2)
                # 시간이 2초 이상이면 화면 캡쳐
                if time.time() - start_time >= 2 :
                    cv2.imwrite(f'./image/capture_{time.time()}.png',img)
                    # 캡쳐 후 counter 추가
                    text_counter += 1
                # counter가 1보다 크면 실행
                for i in range(text_counter):
                    cv2.putText(img, 'captured', org=(30,100), fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=1, color=(225, 0, 225), thickness=2)
                    if text_counter >= 2:
                        text_counter = 0
        
        cv2.putText(img, f'Action: ', org=(100, 450), fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=1, color=(255, 255, 255), thickness=2)

        cv2.imshow('img', img)
        if cv2.waitKey(1) == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

@app.route('/video_feed')
def video_feed():
    global cap
    if Response(gen(cap),mimetype='multipart/x-mixed-replace; boundary=frame'):
        return render_template("camera.html")    # 윈도우창이 출력시 카메라 페이지로 다시 돌아간다 
        
if __name__ == "__main__":
    app.run( debug = True)
