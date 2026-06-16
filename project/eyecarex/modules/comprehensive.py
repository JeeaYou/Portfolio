import cv2
import cvzone
from cvzone.FaceMeshModule import FaceMeshDetector
import mediapipe as mp
from PIL import ImageFont
from modules.eyeTest_Module import (
    overlay_png, overlay_jpg, text_box, save_results, 
    overlay_next_test_screen, overlay_test_result_screen, 
    draw_banner_with_text)
import datetime
import time

# ---------- 헬퍼 ----------
def hit(pt, center, half):  # (x,y) 버튼 히트 테스트
    return abs(pt[0]-center[0]) < half and abs(pt[1]-center[1]) < half

def eyeTest(userID, guide_message, d_start, d_end, selectionSpeed, disease_name, img_url, window_name):
    
    nowDatetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cap = cv2.VideoCapture(0)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    w2, h2 = width//2, height//2
    
    btn_size = width // 10                              # 버튼 사이즈
    half = btn_size // 2

    btn_y = int(height * 0.75)
    btnL_x = int(w2 * 0.75)
    btnR_x = int(w2 * 1.25)
    buttons = [
        {'val': disease_name, 'pos': (btnL_x, btn_y), 'img': '../static/button/yes.png'},
        {'val': '정상', 'pos': (btnR_x, btn_y), 'img': '../static/button/no.png'}
    ]
    detector = FaceMeshDetector(maxFaces=1)
    hands = mp.solutions.hands.Hands(
        max_num_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5
    )
    
    font = ImageFont.truetype('../static/fonts/H2GSRB.TTF', 20)
    logo = cv2.imread('../static/button/logo.png', cv2.IMREAD_UNCHANGED)
    background = cv2.resize(cv2.imread('../static/image/background.jpg'),(width, height))
    img_test = cv2.resize(cv2.imread(img_url),(w2, h2))
    img_textbox = cv2.imread('../static/image/textbox.png', cv2.IMREAD_UNCHANGED)

    counter = 0                                         # 버튼 클릭 시간
    answer = False                                      # 테스트 여부
    List = [] 
    testEnd = False                                     # 테스트 종료
    next_test = False                                     # 왼쪽눈 테스트 시작
    eye = '오른쪽눈'
    
    while True:        
        if cap.get(cv2.CAP_PROP_POS_FRAMES) == cap.get(cv2.CAP_PROP_FRAME_COUNT):
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        success, frame = cap.read()
        
        # frame = cv2.flip(frame, 1)      # 카메라 좌우반전 
        frame, faces = detector.findFaceMesh(frame, draw=False)
        results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        if faces:
            face = faces[0]
            pointLeft = face[145]   # 왼쪽 눈
            pointRight = face[374]  # 오른쪽 눈
            
            # 거리측정코드
            w, _ = detector.findDistance(pointLeft, pointRight)   # 픽셀 거리
            W = 6.3     # 실제 사람 눈 사이 평균 거리(cm)
            f = 400     # 카메라 초점거리 (pixel 단위)840
            distance = (W * f) / w     # 카메라와의 거리

            if d_start < int(distance) <= d_end:        # 60~70 중코드가 보인다
                d_color = (255, 0, 255)          
                overlay_jpg(frame, img_test, w2, h2)   
    
                if results.multi_hand_landmarks:  
                    H, W = frame.shape[:2]                 
                    for hand in results.multi_hand_landmarks:
                        fx, fy = int(hand.landmark[8].x * W), int(hand.landmark[8].y * H)
                        cv2.circle(frame, (fx, fy), 5, (255, 0, 255), -1, cv2.LINE_AA)
                        
                        # 모든 버튼을 하나의 루프에서 처리
                        hit_any = False
                        for btn in buttons:
                            if hit((fx,fy), btn['pos'], half):
                                hit_any = True
                                counter += 1
                                cv2.ellipse(frame, btn['pos'], (half, half), 0, 0, counter * selectionSpeed, (255, 0, 255), 10)
                                if counter * selectionSpeed == 360:
                                    answer = btn['val']
                                    timeStart = time.time()
                                    List = save_results(userID, nowDatetime, eye, answer, List, disease_name)
                                    counter = 0
                                    if len(List) == 1 and eye == '오른쪽눈':
                                        next_test = True
                                    elif len(List) >= 2:
                                        testEnd = True
                        
                        if not hit_any:
                            counter = 0

            else:
                d_color = (200,200,200)  
                
            draw_banner_with_text(frame, width, height, font, guide_message)        
            overlay_png(frame, *(20,20), half //2, half//2, logo) 
            
            # 거리cm
            text = f' {int(distance)}cm '
            (font_w, font_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_PLAIN, 2, 2)
            center_x = (width - font_w) // 2  # 화면 중앙 - 텍스트 폭 절반
            center_y = height // 4            # y 위치
            cvzone.putTextRect(frame, text, (center_x, center_y), scale=2, colorR=d_color)
            
            # 답 구역
            for btn in buttons:
                overlay_png(frame, *btn['pos'], half, half, cv2.imread(btn['img'], cv2.IMREAD_UNCHANGED))
            
            # 왼쪽눈 / 오른쪽눈 표기
            overlay_png(frame, *(int(width*0.13), int(height*0.82)), btn_size, height//15, img_textbox)
            text_box(frame, int(btn_size*0.75), int(height*0.8), eye, font, (0, 0, 0))

        if testEnd:         # 검사결과
            if overlay_test_result_screen(frame, background, disease_name, List, timeStart, height, w2, h2, font):
                break  

        elif next_test:     # 다음 테스트 창
            if overlay_next_test_screen(frame, background, timeStart, height , w2, h2, eye):
                next_test = False
            eye = '왼쪽눈'
        
        cv2.imshow(window_name, frame)
        key = cv2.waitKey(1)
        if key in (27, ord('q')):
            break
            
    print(List)
    print('저장 완료됬습니다.')
    cv2.destroyAllWindows()
    cap.release()