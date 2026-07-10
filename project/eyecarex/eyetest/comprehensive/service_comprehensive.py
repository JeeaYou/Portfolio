# project/eyecarex/eyetest/comprehensive/service_comprehensive.py

from flask import (
    render_template,
    Response,
    current_app,
    abort,
    stream_with_context,
)

from . import bp

import os
import cv2
import time
import datetime
import numpy as np

from cvzone.FaceMeshModule import FaceMeshDetector
from cvzone.HandTrackingModule import HandDetector
from PIL import ImageFont

from ...common.services import (
    get_lang,
    overlay_png,
    overlay_jpg,
    text_box,
    save_results,
    overlay_next_test_screen,
    overlay_test_result_screen,
    draw_banner_with_text,
)


TEMPLATES = {
    "astigmatism": "astigmatism.html",
    "glaucoma": "glaucoma.html",
    "maculopathy": "maculopathy.html",
}


# 여기에서는 lang을 직접 사용하지 않는다.
# 실제 언어 선택은 cam() 함수가 실행될 때 처리한다.
TESTS = {
    "astigmatism": {
        "name": {
            "ko": "난시",
            "en": "Astigmatism",
        },
        "img_rel": (
            "image",
            "astigmatism",
            "pikacyu.jpg",
        ),
        "guide": {
            "ko": (
                "{ds}~{de}cm 거리에서 "
                "피카츄가 또렷하게 보이십니까?"
            ),
            "en": (
                "Can you see Pikachu clearly "
                "at a distance of {ds}~{de}cm?"
            ),
        },

        # 피카츄가 선명하게 보이면 정상
        "yes_is_normal": True,
    },

    "glaucoma": {
        "name": {
            "ko": "녹내장",
            "en": "Glaucoma",
        },
        "img_rel": (
            "image",
            "glaucoma",
            "glaucoma.jpg",
        ),
        "guide": {
            "ko": (
                "이미지와 같은 자세로 정면을 바라보고 "
                "손이 보이나요?\n"
                "보이면 V, 보이지 않으면 X를 선택하세요."
            ),
            "en": (
                "Look straight ahead in the same position "
                "as the image.\n"
                "Select V if you can see your hand, "
                "or X if you cannot."
            ),
        },

        # 손이 보이면 정상
        "yes_is_normal": True,
    },

    "maculopathy": {
        "name": {
            "ko": "황반변성",
            "en": "Macular degeneration",
        },
        "img_rel": (
            "image",
            "maculopathy",
            "baduk.jpg",
        ),
        "guide": {
            "ko": (
                "격자가 휘어지거나 일그러져 보이거나,\n"
                "중앙에 검은 점이 보이십니까?"
            ),
            "en": (
                "Does the grid look distorted or warped,\n"
                "or do you see a black spot in the center?"
            ),
        },

        # 격자 왜곡이나 검은 점이 보이면 황반변성 의심
        "yes_is_normal": False,
    },
}


@bp.get("/<disease>", endpoint="show")
def show(disease):
    lang = get_lang()

    template = TEMPLATES.get(disease)

    if template is None:
        abort(404)

    return render_template(
        template,
        disease=disease,
        lang=lang,
    )


def read_image(
    path,
    flag=cv2.IMREAD_UNCHANGED,
    name="이미지",
):
    img = cv2.imread(path, flag)

    if img is None:
        raise FileNotFoundError(
            f"{name}를 읽을 수 없습니다: {path}"
        )

    return img


def hit(point, center, half):
    return (
        abs(point[0] - center[0]) < half
        and abs(point[1] - center[1]) < half
    )


@bp.get("/<disease>/cam", strict_slashes=False)
def cam(disease):
    lang = get_lang()

    # 현재 코드에서는 한국어가 아니면 영어를 사용한다.
    lang_key = "ko" if lang == "ko" else "en"

    cfg = TESTS.get(disease)

    if cfg is None:
        abort(404)

    d_start = 40
    d_end = 100

    # project/eyecarex/static
    eyecarex_dir = current_app.blueprints[
        "eyecarex"
    ].static_folder

    # project/eyecarex/eyetest/comprehensive/static
    static_dir = bp.static_folder

    img_path = os.path.join(
        static_dir,
        *cfg["img_rel"],
    )

    disease_name = cfg["name"][lang_key]

    normal_name = (
        "정상"
        if lang_key == "ko"
        else "Normal"
    )

    guide_message = cfg["guide"][lang_key].format(
        ds=d_start,
        de=d_end,
    )

    # Yes/No 버튼의 실제 결과를 검사별로 설정
    if cfg["yes_is_normal"]:
        yes_result = normal_name
        no_result = disease_name
    else:
        yes_result = disease_name
        no_result = normal_name

    # 스트리밍 Generator 안에서 current_app을
    # 직접 호출하지 않도록 logger를 미리 저장한다.
    app_logger = current_app.logger

    def gen():
        now_datetime = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            raise RuntimeError(
                "Can't open camera."
            )

        width = int(
            cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        ) or 1280

        height = int(
            cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        ) or 720

        w2 = width // 2
        h2 = height // 2

        btn_size = width // 10
        half = btn_size // 2

        detector = FaceMeshDetector(
            maxFaces=1
        )

        hand_detector = HandDetector(
            maxHands=1,
            detectionCon=0.5,
        )

        # ----------------------------
        # 공통 리소스 경로
        # ----------------------------
        font_path = os.path.join(
            eyecarex_dir,
            "fonts",
            "H2GSRB.TTF",
        )

        bg_path = os.path.join(
            eyecarex_dir,
            "image",
            "background.jpg",
        )

        logo_path = os.path.join(
            eyecarex_dir,
            "image",
            "logo.png",
        )

        textbox_path = os.path.join(
            eyecarex_dir,
            "image",
            "textbox.png",
        )

        yes_path = os.path.join(
            eyecarex_dir,
            "button",
            "yes.png",
        )

        no_path = os.path.join(
            eyecarex_dir,
            "button",
            "no.png",
        )

        # ----------------------------
        # 리소스 불러오기
        # ----------------------------
        if not os.path.exists(font_path):
            raise FileNotFoundError(
                f"Font file not found: {font_path}"
            )

        font = ImageFont.truetype(
            font_path,
            20,
        )

        background_raw = read_image(
            bg_path,
            cv2.IMREAD_COLOR,
            "background 이미지",
        )

        logo = read_image(
            logo_path,
            cv2.IMREAD_UNCHANGED,
            "logo 이미지",
        )

        img_textbox = read_image(
            textbox_path,
            cv2.IMREAD_UNCHANGED,
            "textbox 이미지",
        )

        yes_img = read_image(
            yes_path,
            cv2.IMREAD_UNCHANGED,
            "yes 버튼 이미지",
        )

        no_img = read_image(
            no_path,
            cv2.IMREAD_UNCHANGED,
            "no 버튼 이미지",
        )

        background = cv2.resize(
            background_raw,
            (width, height),
        )

        # ----------------------------
        # 검사 이미지 불러오기
        # ----------------------------
        src = cv2.imread(
            img_path,
            cv2.IMREAD_COLOR,
        )

        if src is None:
            app_logger.error(
                "[comprehensive.cam] "
                "Test image not found: %s",
                img_path,
            )

            src = 255 * np.ones(
                (h2, w2, 3),
                dtype=np.uint8,
            )

        img_test = cv2.resize(
            src,
            (w2, h2),
        )

        # ----------------------------
        # 버튼 위치
        # ----------------------------
        btn_y = int(height * 0.75)

        btn_left_x = int(
            w2 * 0.75
        )

        btn_right_x = int(
            w2 * 1.25
        )

        buttons = [
            {
                "result": yes_result,
                "pos": (
                    btn_left_x,
                    btn_y,
                ),
                "img": yes_img,
            },
            {
                "result": no_result,
                "pos": (
                    btn_right_x,
                    btn_y,
                ),
                "img": no_img,
            },
        ]

        # ----------------------------
        # 검사 상태
        # ----------------------------
        counter = 0
        active_button = None

        result_list = []

        test_end = False
        next_test = False

        # 첫 번째 검사는 오른쪽 눈
        eye = (
            "오른쪽눈"
            if lang_key == "ko"
            else "Right eye"
        )

        time_start = time.time()

        selection_speed = 8
        user_id = "000000001"

        try:
            while True:
                ok, frame = cap.read()

                if not ok:
                    app_logger.warning(
                        "[comprehensive.cam] "
                        "Failed to read camera frame."
                    )
                    break

                # 거울처럼 보이도록 좌우 반전
                frame = cv2.flip(
                    frame,
                    1,
                )

                frame, faces = detector.findFaceMesh(
                    frame,
                    draw=False,
                )

                hands, frame = hand_detector.findHands(
                    frame,
                    draw=False,
                    flipType=False,
                )

                distance = None
                distance_color = (
                    200,
                    200,
                    200,
                )

                # ----------------------------
                # 얼굴 거리 측정
                # ----------------------------
                if faces:
                    face = faces[0]

                    try:
                        left_eye_point = face[145]
                        right_eye_point = face[374]

                        eye_width_pixel, _ = (
                            detector.findDistance(
                                left_eye_point,
                                right_eye_point,
                            )
                        )

                        if (
                            eye_width_pixel
                            and eye_width_pixel > 0
                        ):
                            real_eye_width_cm = 6.3
                            focal_length_pixel = 400

                            distance = (
                                real_eye_width_cm
                                * focal_length_pixel
                            ) / eye_width_pixel

                    except (
                        IndexError,
                        TypeError,
                        ValueError,
                        ZeroDivisionError,
                    ):
                        distance = None

                # ----------------------------
                # 적정 거리 여부
                # ----------------------------
                in_distance = (
                    distance is not None
                    and d_start
                    < int(distance)
                    <= d_end
                )

                if in_distance:
                    distance_color = (
                        255,
                        0,
                        255,
                    )

                    overlay_jpg(
                        frame,
                        img_test,
                        w2,
                        h2,
                    )

                # ----------------------------
                # 손가락 버튼 선택
                # ----------------------------
                can_select = (
                    in_distance
                    and not next_test
                    and not test_end
                )

                if can_select and hands:
                    hand = hands[0]
                    landmark_list = hand.get(
                        "lmList",
                        [],
                    )

                    if len(landmark_list) > 8:
                        finger_x = landmark_list[8][0]
                        finger_y = landmark_list[8][1]

                        cv2.circle(
                            frame,
                            (
                                finger_x,
                                finger_y,
                            ),
                            5,
                            (
                                255,
                                0,
                                255,
                            ),
                            -1,
                            cv2.LINE_AA,
                        )

                        hovered_button = None

                        for index, btn in enumerate(
                            buttons
                        ):
                            if hit(
                                (
                                    finger_x,
                                    finger_y,
                                ),
                                btn["pos"],
                                half,
                            ):
                                hovered_button = index

                                # 다른 버튼으로 이동했으면
                                # 진행도를 처음부터 다시 시작
                                if active_button != index:
                                    active_button = index
                                    counter = 0

                                counter += 1

                                progress = (
                                    counter
                                    * selection_speed
                                )

                                cv2.ellipse(
                                    frame,
                                    btn["pos"],
                                    (
                                        half,
                                        half,
                                    ),
                                    0,
                                    0,
                                    min(
                                        progress,
                                        360,
                                    ),
                                    (
                                        255,
                                        0,
                                        255,
                                    ),
                                    10,
                                )

                                if progress >= 360:
                                    answer = btn[
                                        "result"
                                    ]

                                    result_list = (
                                        save_results(
                                            user_id,
                                            now_datetime,
                                            eye,
                                            answer,
                                            result_list,
                                            disease_name,
                                            eyecarex_dir,
                                        )
                                    )

                                    counter = 0
                                    active_button = None
                                    time_start = time.time()

                                    if len(result_list) == 1:
                                        next_test = True

                                    elif len(result_list) >= 2:
                                        test_end = True

                                break

                        if hovered_button is None:
                            counter = 0
                            active_button = None

                    else:
                        counter = 0
                        active_button = None

                else:
                    counter = 0
                    active_button = None

                # ----------------------------
                # 상단 안내 문구
                # ----------------------------
                draw_banner_with_text(
                    frame,
                    width,
                    height,
                    font,
                    guide_message,
                )

                # ----------------------------
                # 로고
                # ----------------------------
                overlay_png(
                    frame,
                    20,
                    20,
                    half // 2,
                    half // 2,
                    logo,
                )

                # ----------------------------
                # 거리 표시
                # ----------------------------
                if distance is not None:
                    distance_text = (
                        f" {int(distance)}cm "
                    )
                else:
                    distance_text = " --cm "

                (
                    text_width,
                    text_height,
                ), _ = cv2.getTextSize(
                    distance_text,
                    cv2.FONT_HERSHEY_PLAIN,
                    2,
                    2,
                )

                distance_x = (
                    width - text_width
                ) // 2

                distance_y = height // 4

                cv2.rectangle(
                    frame,
                    (
                        distance_x - 8,
                        distance_y
                        - text_height
                        - 8,
                    ),
                    (
                        distance_x
                        + text_width
                        + 8,
                        distance_y + 8,
                    ),
                    (
                        0,
                        0,
                        0,
                    ),
                    -1,
                )

                cv2.putText(
                    frame,
                    distance_text,
                    (
                        distance_x,
                        distance_y,
                    ),
                    cv2.FONT_HERSHEY_PLAIN,
                    2,
                    distance_color,
                    2,
                    cv2.LINE_AA,
                )

                # ----------------------------
                # Yes / No 버튼
                # ----------------------------
                for btn in buttons:
                    overlay_png(
                        frame,
                        btn["pos"][0],
                        btn["pos"][1],
                        half,
                        half,
                        btn["img"],
                    )

                # ----------------------------
                # 현재 검사 중인 눈 표시
                # ----------------------------
                overlay_png(
                    frame,
                    int(width * 0.13),
                    int(height * 0.82),
                    btn_size,
                    height // 15,
                    img_textbox,
                )

                text_box(
                    frame,
                    int(btn_size * 0.75),
                    int(height * 0.8),
                    eye,
                    font,
                    (
                        0,
                        0,
                        0,
                    ),
                )

                # ----------------------------
                # 최종 결과 화면
                # ----------------------------
                if test_end:
                    should_break = (
                        overlay_test_result_screen(
                            frame,
                            background,
                            disease_name,
                            result_list,
                            time_start,
                            height,
                            w2,
                            h2,
                            font,
                            eyecarex_dir,
                        )
                    )

                    if should_break:
                        break

                # ----------------------------
                # 다음 눈 검사 안내 화면
                # ----------------------------
                elif next_test:
                    should_next = (
                        overlay_next_test_screen(
                            frame,
                            background,
                            time_start,
                            height,
                            w2,
                            h2,
                            eye,
                            eyecarex_dir,
                        )
                    )

                    if should_next:
                        next_test = False

                        eye = (
                            "왼쪽눈"
                            if lang_key == "ko"
                            else "Left eye"
                        )

                        counter = 0
                        active_button = None
                        time_start = time.time()

                # ----------------------------
                # 영상 스트리밍
                # ----------------------------
                encode_ok, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                )

                if not encode_ok:
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + buffer.tobytes()
                    + b"\r\n"
                )

        finally:
            cap.release()

    return Response(
        stream_with_context(gen()),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        ),
    )