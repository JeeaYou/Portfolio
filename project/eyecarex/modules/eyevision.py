import cv2, time, datetime, cvzone
from cvzone.FaceMeshModule import FaceMeshDetector
import mediapipe as mp
from PIL import ImageFont
from modules.eyeTest_Module import (
    overlay_png, overlay_jpg, text_box, save_results, 
    overlay_next_test_screen, overlay_test_result_screen,draw_banner_with_text)
from modules.eyeVision_Module import (
    make_eyeChart, get_eyeImg, answer_true_false, load_next_image, 
    result_checking)

# ------------------ 헬퍼 ------------------
def hit(p, center, half):  # 히트 테스트
    x, y = p; cx, cy = center
    return abs(x - cx) < half and abs(y - cy) < half

# ------------------ 본 함수 ------------------
def eyeTest(userID, guide_message, d_start, d_end, selectionSpeed, disease_name, window_name, max_test_count):
    nowDatetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cap = cv2.VideoCapture(0)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w2, h2 = width//2, height//2
    btn_size  = width//10
    half      = btn_size//2

    detector = FaceMeshDetector(maxFaces=1)
    hands = mp.solutions.hands.Hands(max_num_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5)

    # 리소스(루프 밖)
    font = ImageFont.truetype('../static/fonts/H2GSRB.TTF', 20)
    logo = cv2.imread('../static/button/logo.png', cv2.IMREAD_UNCHANGED)
    background = cv2.resize(cv2.imread('../static/image/background.jpg'), (width, height))
    img_textbox = cv2.imread('../static/image/textbox.png', cv2.IMREAD_UNCHANGED)

    # 방향 아이콘
    base = cv2.imread('../static/button/left.png', cv2.IMREAD_UNCHANGED)  
    icons = {
        'left' : base,
        'right': cv2.rotate(base, cv2.ROTATE_180),
        'up'   : cv2.rotate(base, cv2.ROTATE_90_CLOCKWISE),
        'down' : cv2.rotate(base, cv2.ROTATE_90_COUNTERCLOCKWISE),
    }

    # 버튼 배치(라벨, 좌표팩터, 아이콘)
    buttons = [
        ('left',  (int(width * 0.30), int(h2 * 1.15))),
        ('right', (int(width * 0.70), int(h2 * 1.15))),
        ('up',    (w2, int(height * 0.30))),
        ('down',  (w2, int(height * 0.83))),
    ]

    # 시력도표 데이터
    dataList = make_eyeChart()
    level, max_level = int(dataList['등급'].min()), int(dataList['등급'].max())
    answer_list, test_count, wrong_cnt = [], 0, 0
    mode, finish, next_test, testEnd = 'normal', False, False, False
    eye = '오른쪽눈'
    img_name, img_level, img_eyelevel, img_url = get_eyeImg(level, dataList)
    img_test = cv2.resize(cv2.imread(img_url), (h2, h2))
    List = []

    counter = 0
    timeStart = time.time()

    while True:
        ok, frame = cap.read()
        if not ok: break

        # FaceMesh + Hands (RGB 왕복 1회)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame, faces = detector.findFaceMesh(frame, draw=False)   # detector가 BGR을 반환
        results = hands.process(rgb)

        if faces:
            face = faces[0]
            pointLeft, pointRight = face[145], face[374]
            w_dist, _ = detector.findDistance(pointLeft, pointRight)
            W, f = 6.3, 400
            distance = (W * f) / w_dist

            # 거리 OK 구간
            in_range = d_start < int(distance) <= d_end
            d_color = (255, 0, 255) if in_range else (200, 200, 200)

            if in_range:
                overlay_jpg(frame, img_test, w2, int(h2 * 1.15))
                if results.multi_hand_landmarks:
                    h_img, w_img = frame.shape[:2]
                    for hand in results.multi_hand_landmarks:
                        fx, fy = int(hand.landmark[8].x * w_img), int(hand.landmark[8].y * h_img)
                        cv2.circle(frame, (fx, fy), 5, (255, 0, 255), -1, cv2.LINE_AA)

                        # 모든 버튼을 하나의 루프로 처리
                        for label, center in buttons:
                            if hit((fx, fy), center, half):
                                counter += 1
                                cv2.ellipse(frame, center, (half, half), 0, 0, counter * selectionSpeed, (255,0,255), 10)
                                if counter * selectionSpeed == 360:
                                    answer, level, mode, wrong_cnt, answer_list, test_count, finish = \
                                        answer_true_false(label, img_name, img_eyelevel, img_level,
                                                          answer_list, mode, level, wrong_cnt,
                                                          max_level, test_count, max_test_count)
                                    timeStart = time.time()
                                    img_name, img_level, img_eyelevel, img_url, img_test = \
                                        load_next_image(level, dataList, h2, h2)
                                break
                        else:
                            counter = 0  # 어떤 버튼에도 히트 안됨

                        if finish:
                            level = 1
                            answer = result_checking(answer_list)
                            finish = False
                            List = save_results(userID, nowDatetime, eye, answer, List, disease_name)
                            timeStart = time.time()
                            next_test = (len(List) == 1)
                            testEnd   = (len(List) == 2)

            # 상단 거리 표기
            (w, h), _ = cv2.getTextSize(f' {int(distance)}cm ', cv2.FONT_HERSHEY_PLAIN, 2, 2)
            x = (frame.shape[1] - w)//2
            cvzone.putTextRect(frame, f' {int(distance)}cm ', (x, height//5), scale=2, colorR=d_color)

            # 로고/지시문
            draw_banner_with_text(frame, width, height, font, guide_message)        
            overlay_png(frame, *(20, 20), half//2, half//2, logo)

            # 버튼 오버레이(통일)
            for label, center in buttons:
                overlay_png(frame, *center, half, half, icons[label])

            # 왼쪽/오른쪽 눈
            overlay_png(frame, *(int(width*0.13), int(height*0.82)), btn_size, height//15, img_textbox)
            text_box(frame, int(btn_size*0.75), int(height*0.8), eye, font, (0, 0, 0))

            # 결과/다음 테스트 화면
            if testEnd and len(List) == 2:
                if overlay_test_result_screen(frame, background, disease_name, List, timeStart, height, w2, h2, font):
                    break
            elif next_test:
                if overlay_next_test_screen(frame, background, timeStart, height, w2, h2, eye):
                    # 다음 라운드 초기화
                    next_test = False
                    eye = '왼쪽눈'
                    level, wrong_cnt, test_count, mode, counter = 1, 0, 0, 'normal', 0
                    answer_list = []
                    img_name, img_level, img_eyelevel, img_url, img_test = load_next_image(level, dataList, h2, h2)

        cv2.imshow(window_name, frame)
        key = cv2.waitKey(1)
        if key in (27, ord('q')):
            break

    cv2.destroyAllWindows()
    cap.release()