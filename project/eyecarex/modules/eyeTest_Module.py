from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
import pandas as pd
import time
import os

# 안내 문구
def draw_banner_with_text(frame, width, height, font, text):
    banner_h = int(height * 0.12)   # 배너 높이
    alpha = 0.6                     # 배경 투명도

    # 배너용 레이어
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (width, banner_h), (0, 0, 0), cv2.FILLED)
    frame[:] = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

    # 안내 문구 출력
    text_box(frame, None, int(banner_h*0.20), text, font, (255, 255, 255))

# png 이미지 추가
def overlay_png(frame, x, y, w, h, overlay_image): # 대상 이미지 (3채널), x, y 좌표, width, height, 덮어씌울 이미지 (4채널:투명도를 가짐)
    img_h, img_w = frame.shape[:2]

    # 1. 먼저 원하는 크기로 overlay 이미지 고정
    overlay_resized = cv2.resize(overlay_image, (w * 2, h * 2))  # 중심 기준이므로 *2

    # 2. 붙일 영역 계산
    y1 = max(0, y - h)
    y2 = min(img_h, y + h)
    x1 = max(0, x - w)
    x2 = min(img_w, x + w)

    # 3. overlay에서 붙일 부분 계산 (잘린 만큼 offset 적용)
    oy1 = max(0, - (y - h))
    oy2 = oy1 + (y2 - y1)
    ox1 = max(0, - (x - w))
    ox2 = ox1 + (x2 - x1)

    if y1 >= y2 or x1 >= x2:
        return  # 화면 밖이면 안 그림

    # 4. 알파 채널 분리
    alpha = overlay_resized[oy1:oy2, ox1:ox2, 3] / 255.0

    for c in range(3):
        frame[y1:y2, x1:x2, c] = (
            overlay_resized[oy1:oy2, ox1:ox2, c] * alpha +
            frame[y1:y2, x1:x2, c] * (1 - alpha)
        )

        
# jpg이미지 중앙 정렬 및 사이즈 설정
def overlay_jpg(image, def_img, img_x, img_y):
    h, w, _ = def_img.shape
    img_h, img_w = image.shape[:2]

    # 중심 좌표를 화면 범위 안으로 제한
    img_x = min(max(img_x, w // 2), img_w - w // 2)
    img_y = min(max(img_y, h // 2), img_h - h // 2)

    y1 = int(img_y - h / 2)
    y2 = int(img_y + h / 2)
    x1 = int(img_x - w / 2)
    x2 = int(img_x + w / 2)

    image[y1:y2, x1:x2] = def_img
    
# 텍스트 박스
def text_box(image, x=None, y=None, text="", font=None, color=(0, 0, 0)):
    img_pil = Image.fromarray(image)
    draw = ImageDraw.Draw(img_pil)
    
    img_w, img_h = image.shape[1], image.shape[0]
    text_w, text_h = draw.textsize(text, font=font)

    if x is None and y is None:
        # 중앙 정렬
        xy = ((img_w - text_w) // 2, (img_h - text_h) // 2)
    elif x is None:
        # y만 지정 → x는 중앙
        xy = ((img_w - text_w) // 2, y)
    elif y is None:
        # x만 지정 → y는 중앙
        xy = (x, (img_h - text_h) // 2)
    else:
        # x, y 둘 다 지정
        xy = (x, y)

    draw.text(xy=xy, text=text, font=font, fill=color)
    image[:] = np.array(img_pil)
    
# 파일 저장
def save_results(userID, nowDatetime, eye, answer, List, disease_name):
    List.append({
        'ID':userID,
        '시간':nowDatetime,
        '눈':eye,
        '여부':answer
    })  
    df = pd.DataFrame(List)
    out_dir = '../static/csv파일'
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(f'../static/csv파일/{disease_name}.csv')
    return List

# 계속 검사 창
def overlay_next_test_screen(image, background, timeStart, height , width_h, height_h, eye):
    overlay_jpg(image, background, width_h, height_h)
    
    # Display "continue the test" message
    text_box(image, None, int(height * 0.35), 
             '검사 계속하기', 
             ImageFont.truetype('../static/fonts/H2GSRB.TTF', height // 10), (0, 0, 0))
    
    # Countdown for the next test
    text_box(image, None, int(height * 0.6), 
             f'{int(6-(time.time()-timeStart))}초후 {eye} 검사 시작합니다.',
             ImageFont.truetype('../static/fonts/H2GSRB.TTF', height_h // 10), (0, 0, 0))
    
    # If 6 seconds have passed, start the left-eye test
    if int(6 - (time.time() - timeStart)) == 0:
        return True  # Move to the next test
    return False
    

# 검사 결과 창
def overlay_test_result_screen(image, background, disease_name, List, timeStart, height, width_h, height_h, font):
    overlay_jpg(image, background, width_h, height_h)
    
    # Display the test result title
    text_box(image, None, int(height * 0.3), 
             f"{disease_name} 검사 결과", 
             ImageFont.truetype('../static/fonts/H2GSRB.TTF', height // 10),  (0, 0, 0))
    
    # Display results for each eye
    text_box(image, None, int(height * 0.5), 
             f"{List[0]['눈']}: {List[0]['여부']} ", 
             font,  (0, 0, 0))
    text_box(image, None, int(height * 0.5) + 30, 
             f"{List[1]['눈']}: {List[1]['여부']} ", 
             font,  (0, 0, 0))
    
    # Countdown for test end
    text_box(image, None, int(height * 0.7), 
             f'{int(11-(time.time()-timeStart))} 초 후 검사 종료합니다.',
             ImageFont.truetype('../static/fonts/H2GSRB.TTF', height_h // 10), (0, 0, 0))
    
    # If 10 seconds have passed, end the test
    if int(11 - (time.time() - timeStart)) == 0:
        return True  # End the test
    return False