import os
import random
import cv2
from cvzone.FaceMeshModule import FaceMeshDetector
import cvzone
from PIL import ImageFont
from modules.eyeTest_Module import overlay_png, overlay_jpg, text_box, draw_banner_with_text
import mediapipe as mp
import pandas as pd
import time
import datetime

def eye_blink_game(userID, guide_message, totalTime, window_name):

    nowDatetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cap = cv2.VideoCapture(0)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w2, h2 = width//2, height//2
    btn_size  = width // 10

    detector = FaceMeshDetector(maxFaces=1)
    mp_hands = mp.solutions.hands

    font = ImageFont.truetype('../static/fonts/H2GSRB.TTF', 20)
    logo = cv2.imread('../static/button/logo.png', cv2.IMREAD_UNCHANGED)
    background = cv2.resize(cv2.imread('../static/image/background.jpg'), (width, height))
    img_start = cv2.imread('../static/button/start.png', cv2.IMREAD_UNCHANGED)
    img_textbox = cv2.imread('../static/image/textbox.png', cv2.IMREAD_UNCHANGED)

    # import images
    folderBirds = '../static/image/game/'
    ListBirds = os.listdir(folderBirds)
    catch = []
    for object in ListBirds:
        catch.append(cv2.resize(cv2.imread(f'{folderBirds}/{object}', cv2.IMREAD_UNCHANGED),(btn_size, btn_size)))

    currentObject = catch[0]
    pos = [random.randint(0, max(0, width - btn_size)), 0]
    speed = random.randint(5, 5)
    count = 0
    
    # 시간 관련 변수
    timeStart = None
    endTime   = None
    start_btn = (w2, h2)  # (x1,y1,x2,y2)
    # --- 시작 전 상태에서, 루프 바깥(초기화) ---
    press_start = None  # 버튼 누르기 시작한 시각 (None이면 미눌림)
    HOLD_SEC = 2.0      # 2초간 터치

    # 깜빡임 관련
    eye_dist_close, eye_dist_open = 33, 37    
    blink_in_progress = False
    closed_frames = 0
    cooldown = 0            # 깜빡임 직후 재트리거 방지
    CLOSE_MIN_FRAMES = 2    # 최소 닫힘 프레임(노이즈 제거)
    ratioList, score_rows = [], []
    
    # 상태 플래그
    started = False
    gameOver = False
    counting_down = False 
    countdown_end = None 
    
    def resetObject():
        pos[0] = random.randint(0, max(0, width - btn_size))
        pos[1] = 0
        return catch[random.randrange(len(catch))]

    with mp_hands.Hands(max_num_hands=2,min_detection_confidence=0.5,min_tracking_confidence=0.5) as hands:
        while True:
            success, frame = cap.read()
            touching = False
            # --- 아직 시작 전 ---
            if not started and not counting_down:
                draw_banner_with_text(frame, width, height, font, 'START 버튼에 2초간 터치하세요.')        
                overlay_png(frame, *(20, 20), btn_size//4, btn_size//4, logo)

                # 버튼 그리기 (중앙=w2,h2, 반쪽 크기=width//5, height//5)
                half_w, half_h = width//5, height//5
                overlay_png(frame, *(w2, h2), half_w, half_h, img_start)

                # 버튼 사각형(x1,y1,x2,y2) - overlay_png가 중앙/half 크기 기준이라 이렇게 계산
                start_btn = (w2 - half_w, h2 - half_h, w2 + half_w, h2 + half_h)

                # Mediapipe는 RGB 입력 필요
                results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

                # 1) 버튼 안에 손가락 끝(landmark 8)이 있는지 판정
                touching = False
                if results.multi_hand_landmarks:
                    H, W = frame.shape[:2]
                    for hand in results.multi_hand_landmarks:
                        fx, fy = int(hand.landmark[8].x * W), int(hand.landmark[8].y * H)
                        if (start_btn[0] <= fx <= start_btn[2]) and (start_btn[1] <= fy <= start_btn[3]):
                            touching = True
                            break

                # 2) 루프 밖에서 2초 홀드 처리
                if touching:
                    if press_start is None:
                        press_start = time.time()
                    held = time.time() - press_start

                    # 진행률 원호(선택)
                    progress = min(360, int(360 * (held / HOLD_SEC)))
                    cv2.ellipse(frame, (w2, h2), (half_w, half_h), 0, 0, progress, (255, 0, 255), 8)

                    if held >= HOLD_SEC:
                        counting_down = True
                        countdown_end = time.time() + 5.0  # 3초 카운트다운
                        press_start = None
                else:
                    press_start = None
                    
            # --- 3초 카운트다운 ---
            elif counting_down and not started:
                draw_banner_with_text(frame, width, height, font, guide_message)        
                overlay_png(frame, *(20, 20), btn_size//4, btn_size//4, logo)
                
                remain = countdown_end - time.time()
                if remain > 0:
                    sec = int(remain) + 1  # 2.4s→3, 1.7s→2 처럼 보이도록
                    big_font = ImageFont.truetype('../static/fonts/H2GSRB.TTF', width // 5)

                    if sec >= 1:
                        text_box(frame, None, None, str(sec), big_font, (255, 0, 255))
                    else:
                        text_box(frame, None, None, "GO!", big_font, (255, 0, 255))
                else:
                    # 카운트다운 종료 시점에 실제 게임 타이머 시작
                    started = True
                    timeStart = time.time()
                    endTime   = timeStart + float(totalTime)
                    counting_down = False

            # --- 게임 시작 ---
            elif not gameOver:
                draw_banner_with_text(frame, width, height, font, guide_message)        
                overlay_png(frame, *(20, 20), btn_size//4, btn_size//4, logo)
                
                # 남은 시간 계산
                remaining = int(endTime - time.time())
                gameOn = remaining >= 0

                if gameOn:
                    frame, faces = detector.findFaceMesh(frame, draw=False)

                    pos[1] += speed
                    if pos[1] > height - btn_size:
                        currentObject = resetObject()
                    else:
                        # 완전-내부일 때만 overlay (좌측/상단/우측/하단 모두 프레임 안)
                        if 0 <= pos[0] <= width - btn_size and 0 <= pos[1] <= height - btn_size:
                            frame = cvzone.overlayPNG(frame, currentObject, pos)
                        else:
                            # 혹시라도 밖으로 나가면 바로 리셋
                            currentObject = resetObject()

                    if faces:
                        face = faces[0]
                        up = face[159]  # Lefteye
                        down = face[23]
                        left = face[130]
                        right = face[243]

                        upDown, _ = detector.findDistance(up, down)
                        leftRight, _ = detector.findDistance(left, right)

                        cx, cy = (up[0] + down[0]) // 2, (up[1] + down[1]) // 2
                        dist, _ = detector.findDistance((cx, cy), (pos[0] + 50, pos[1] + 50))

                        ratio = int((upDown / leftRight) * 100)
                        ratioList.append(ratio)
                        if len(ratioList) > 3:
                            ratioList.pop(0)
                        ratioAvg = sum(ratioList) / len(ratioList)
                        if ratioAvg < eye_dist_close:
                            closed_frames += 1
                        else:
                            closed_frames = 0

                        # 쿨다운 감소
                        if cooldown > 0:
                            cooldown -= 1

                        # 표시용 상태 텍스트
                        # eyeStatus = "CLOSED" if ratioAvg < eye_dist_close else "OPEN"
                        # cv2.putText(frame, eyeStatus, (50, 50),
                        #             cv2.FONT_HERSHEY_COMPLEX, 2, (255, 0, 255), 2)
                        
                        # 1) 열림 상태 -> 닫힘으로 진입(깜빡임 시작)
                        if (not blink_in_progress) and (closed_frames >= CLOSE_MIN_FRAMES) and (cooldown == 0):
                            blink_in_progress = True

                        # 2) 닫힘 상태 -> 다시 열림(깜빡임 완료) 시 한 번만 점수
                        elif blink_in_progress and (ratioAvg > eye_dist_open):
                            currentObject = resetObject()
                            count += 1
                            blink_in_progress = False
                            cooldown = 6

                        overlay_png(frame, *(int(width*0.16), int(height*0.82)), width // 7, height//15, img_textbox)
                        text_box(frame, int(btn_size*0.75), int(height*0.8), f'Score:  {str(count)}', font, (0, 0, 0))
                        text_box(frame, width - 150, 20, f'Time: {remaining}', ImageFont.truetype('../static/fonts/H2GSRB.TTF', h2 // 8), (255, 0, 255), )
                else:
                    gameOver = True   #  추가
                    
            # --- 게임 오버 화면 ---
            else: 
                overlay_jpg(frame, background, w2, h2)

                text_box(frame, None, int(height * 0.35), "Game Over", ImageFont.truetype('../static/fonts/H2GSRB.TTF', height // 10), (0, 0, 0))
                text_box(frame, None, int(height * 0.6), f'Your Score: {str(count)}',font,  (0, 0, 0))
                
                # count down
                after_remaining = max(0, 11 - int(time.time() - endTime))
                text_box(
                    frame, None, int(height * 0.7),
                    f'{after_remaining} 초 후 게임 종료합니다.',
                    ImageFont.truetype('../static/fonts/H2GSRB.TTF', h2 // 10), (0, 0, 0)
                )
                if after_remaining <= 0:
                    break
                
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1)
            if key in (27, ord('q')):
                break
            
    cap.release()
    cv2.destroyAllWindows()
    
    score_rows.append({'ID': userID, '시간': nowDatetime, '점수': str(count)})
    df = pd.DataFrame(score_rows)
    df.to_csv('../static/csv파일/게임.csv')
    print(df)