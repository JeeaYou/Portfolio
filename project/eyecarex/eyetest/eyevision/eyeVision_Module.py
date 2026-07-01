from glob import glob
from pathlib import Path
import pandas as pd
import os
import cv2


def make_eyeChart(curr_dir):
    static_dir = Path(curr_dir).resolve()
    out_dir = static_dir / "csv_file"
    csv_path = out_dir / "eyechart.csv"

    def create_csv():
        dataList = []

        # 0.1 ~ 2.0까지 순서 고정
        eye_levels = [round(i * 0.1, 1) for i in range(1, 21)]
        folders = glob(str(static_dir / "image" / "*"))
        folder_map = {}

        for folder in folders:
            folder_name = Path(folder).name

            try:
                eye_level = round(float(folder_name), 1)
                folder_map[eye_level] = folder
            except ValueError:
                continue

        # 0.1부터 2.0까지 순서대로 CSV 생성
        for idx, eye_level in enumerate(eye_levels, start=1):
            folder = folder_map.get(eye_level)

            # 해당 시력 폴더가 없으면 건너뜀
            if folder is None:
                continue

            imgs = sorted(glob(os.path.join(folder, "*.jpg")))

            for img in imgs:
                img_path = Path(img).resolve()

                dataList.append({
                    "direction": img_path.stem,
                    "visual_acuity": f"{eye_level:.1f}",
                    "level": idx,
                    "path": str(img_path),
                })

        df_new = pd.DataFrame(dataList)

        out_dir.mkdir(parents=True, exist_ok=True)
        df_new.to_csv(csv_path, index=False, encoding="utf-8-sig")

        print("-Created new Eyechart CSV file.")
        return df_new

    return create_csv()

# 랜덤 이미지 가져오기 
def get_eyeImg(level, df):

    available_levels = sorted(
        df["level"].dropna().astype(int).unique().tolist()
    )

    level = int(level)

    # 현재 level에 데이터가 없으면 가장 가까운 level로 보정
    if level not in available_levels:
        higher_levels = [lv for lv in available_levels if lv >= level]
        lower_levels = [lv for lv in available_levels if lv <= level]

        if higher_levels:
            level = higher_levels[0]
        elif lower_levels:
            level = lower_levels[-1]
        else:
            level = available_levels[0]

        print(f"Level adjusted to available level: {level}")

    img_info = df[df["level"].astype(int) == level]

    if img_info.empty:
        raise ValueError(f"No eye chart image found for level {level}.")

    img_row = img_info.sample(1).iloc[0]

    img_name = str(img_row["direction"])
    img_level = int(img_row["level"])
    img_eyelevel = float(img_row["visual_acuity"])
    img_url = str(img_row["path"])

    return img_name, img_level, img_eyelevel, img_url

# 다음 이미지 불러오기
def load_next_image(level, df, w, h):
    img_name, img_level, img_eyelevel, img_url = get_eyeImg(level, df)

    img = cv2.imread(img_url)

    if img is None:
        raise FileNotFoundError(f"Can't read eyechart image : {img_url}")

    img_test = cv2.resize(img, (w, h))

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
    
    # ---- 시도 횟수 증가 ----
    test_count += 1
    
    # ---- 기록 ----
    answer_list.append({
        'visual_acuity': img_eyelevel,
        'level': img_level,
        'direction': img_name,
        'TF': answer_tf,
        'answer': answer,
        'wrongcnt': wrongCnt,
        'testcount': test_count
    })
    
    # --- 클램프 & 종료 조건 ---
    level = max(1, min(level, max_level))
    if level == max_level:
        finish = True
        print("Test Completed : Maximum level reached.")
    elif wrongCnt == 3:
        finish = True
        print("Test ended : 3 consecutive wrong answers.")
    elif test_count >= max_test_count:
        finish = True
        print(f"Test Completed : reached the maximum of {max_test_count} attempts")

    return answer_tf, level, mode, wrongCnt, answer_list, test_count, finish

# 결과 검증 하기
def result_checking(answer_df):
    # 시력 숫자화 + 정답 / 오답 플래그
    df = pd.DataFrame(answer_df).copy()
    # 안전한 숫자 변환 + NaN 제거
    df['visual_acuity'] = pd.to_numeric(df['visual_acuity'], errors='coerce')
    df = df.dropna(subset=['visual_acuity'])
    if df.empty:
        return 'Unable to determine'

    df['correct'] = (df['TF'] == 'true')

    # 최고 시력(정답 중)
    best = df.loc[df['correct']].sort_values(['level', 'visual_acuity']).tail(1)
    best_level = float(best['level'].iat[0]) if not best.empty else None
    best_eye   = float(best['visual_acuity'].iat[0]) if not best.empty else None

    # 구간별 집계
    true_lt_08  = int(((df['visual_acuity'] < 0.8)  & (df['correct'])).sum())
    true_ge_08  = int(((df['visual_acuity'] >= 0.8) & (df['correct'])).sum())
    true_le_10  = int(((df['visual_acuity'] <= 1.0) & (df['correct'])).sum())
    true_ge_10  = int(((df['visual_acuity'] >= 1.0) & (df['correct'])).sum())
    # ‘오답’ 컬럼이 없으면 ~df['correct'] 사용
    false_le_10 = int(((df['visual_acuity'] <= 1.0) & (~df['correct'])).sum())

    # 판정 규칙
    if (best_eye is not None) and (best_eye >= 0.8) and (true_lt_08 > true_ge_08):
        answer = 'Normal'
    elif (true_ge_10 > true_le_10) or ((false_le_10 > true_le_10) and (true_ge_10 > 0)):
        answer = 'Hyperopia'
    else:
        answer = 'Myopia'

    print("=== Result ===")
    print(f"- {answer} , Best visual acuity: {best_eye} (level: {best_level})")
    return answer