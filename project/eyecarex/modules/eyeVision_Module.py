from glob import glob
from pathlib import Path
import pandas as pd
import os
import cv2

# 모든 테스트 가져오기
def make_eyeChart():
    out_dir = Path('../static/csv파일')
    if os.path.exists(out_dir / '시력표.csv'):
        df = pd.read_csv(out_dir / '시력표.csv')
        print("-파일이 이미 존재합니다.")
        
    else :
        dataList = []
        folders = glob('../static/image/eyetest/*')
        for idx, folder in enumerate(folders, start=1):   # 등급 인덱스 부여
            imgs = glob(folder + '/*.jpg')
            for img in imgs:
                name = img.split('\\')[-1].replace('.jpg', '')   # 파일명
                category = img.split('\\')[-2]                   # 폴더명 (등급)

                dataList.append({
                    '방향': name,
                    '시력': category,
                    '등급': idx,     # 등급 인덱스
                    '경로': img
                })

        df = pd.DataFrame(dataList)
        out_dir.mkdir(parents=True, exist_ok=True)   # 폴더 없으면 생성
        df.to_csv(out_dir / '시력표.csv', index=False, encoding='utf-8-sig') # 엑셀 호환 위해 BOM 포함
        print("-생성 완료.")
    return df

# 랜덤 이미지 가져오기
def get_eyeImg(level, df):
    img_info = df[df['등급'] == level].sample(1)
    img_row = img_info.iloc[0]
    
    img_name = str(img_row['방향'])
    img_level = int(img_row['등급'])
    img_eyelevel = float(img_row['시력'])
    img_url = str(img_row['경로'])
    
    return img_name, img_level, img_eyelevel, img_url

# 다음 이미지 불러오기
def load_next_image(level, df, w, h):
    img_name, img_level, img_eyelevel, img_url = get_eyeImg(level, df)
    img_test = cv2.resize(cv2.imread(img_url), (w, h))

    return img_name, img_level, img_eyelevel, img_url, img_test

# 정답 여부
def answer_true_false(answer, img_name, img_eyelevel, img_level,
                      answer_list, mode, level, wrongCnt, max_level, test_count, max_test_count):
    is_correct = (img_name == answer)
    answer_tf = 'true' if is_correct else 'false'
    finish = False
    
    # ---- 정오답에 따른 레벨/오답수 업데이트 ----
    if is_correct:
        # print('true', img_name)
        wrongCnt = 0
        if mode == 'normal':
            level += 2
        else:  # hyperopia
            level += 1

    else:
        # print('false', img_name)
        wrongCnt += 1
        if mode == 'normal':
            level -= 1
            if level < 1:
                level = 1
                mode = 'hyperopia'
        else:  # hyperopia
            level += 1
            wrongCnt = 0
    print(img_level)
    
    # ---- 시도 횟수 증가 ----
    test_count += 1
    
    # ---- 기록 ----
    answer_list.append({
        '시력': img_eyelevel,
        '등급': img_level,
        '방향': img_name,
        'TF': answer_tf,
        '답': answer,
        '연속오답': wrongCnt,
        '누적횟수': test_count
    })
    
    # --- 클램프 & 종료 조건 ---
    level = max(1, min(level, max_level))
    if level == max_level:
        finish = True
        print("테스트 완료(최고 등급 도달)")
    elif wrongCnt == 3:
        finish = True
        print("연속 3번 오답 → 테스트 종료")
    elif test_count >= max_test_count:
        finish = True
        print(f"총 {max_test_count}번 테스트 완료 → 종료")

    return answer_tf, level, mode, wrongCnt, answer_list, test_count, finish

# 결과 검증 하기
def result_checking(answer_df):
    # 시력 숫자화 + 정답 / 오답 플래그
    df = pd.DataFrame(answer_df).copy()
    # 안전한 숫자 변환 + NaN 제거
    df['시력'] = pd.to_numeric(df['시력'], errors='coerce')
    df = df.dropna(subset=['시력'])
    if df.empty:
        return '판정불가'

    df['정답'] = (df['TF'] == 'true')

    # 최고 시력(정답 중)
    best = df.loc[df['정답']].sort_values(['등급', '시력']).tail(1)
    best_level = float(best['등급'].iat[0]) if not best.empty else None
    best_eye   = float(best['시력'].iat[0]) if not best.empty else None

    # 구간별 집계
    true_lt_08  = int(((df['시력'] < 0.8)  & (df['정답'])).sum())
    true_ge_08  = int(((df['시력'] >= 0.8) & (df['정답'])).sum())
    true_le_10  = int(((df['시력'] <= 1.0) & (df['정답'])).sum())
    true_ge_10  = int(((df['시력'] >= 1.0) & (df['정답'])).sum())
    # ‘오답’ 컬럼이 없으면 ~df['정답'] 사용
    false_le_10 = int(((df['시력'] <= 1.0) & (~df['정답'])).sum())

    # 판정 규칙
    if (best_eye is not None) and (best_eye >= 0.8) and (true_lt_08 > true_ge_08):
        answer = '정상'
    elif (true_ge_10 > true_le_10) or ((false_le_10 > true_le_10) and (true_ge_10 > 0)):
        answer = '원시'
    else:
        answer = '근시'

    print("=== 판정 결과 ===")
    print(f"- {answer} , 최고 시력: {best_eye} (등급: {best_level})")
    return answer