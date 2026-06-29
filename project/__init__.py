# project/__init__.py
from flask import Flask, url_for, request, g
import os
from urllib.parse import quote_plus
from types import SimpleNamespace
from pathlib import Path

from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# .env 파일 로드
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env", override=True)

db = SQLAlchemy()

SUPPORTED_LANGS = ["ko", "en", "zh"]
bio_text = "Backend & AI"


def _get_database_uri():
    """
    DB 연결 문자열 생성.
    코드 안에 비밀번호를 직접 쓰지 않기 위해 환경변수를 사용한다.
    """

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_password = os.getenv("MYSQL_PASSWORD", "1q2w3e4r!")
    mysql_host = os.getenv("MYSQL_HOST", "127.0.0.1")
    mysql_port = os.getenv("MYSQL_PORT", "3306")
    mysql_database = os.getenv("MYSQL_DATABASE", "project")

    encoded_password = quote_plus(mysql_password)

    return (
        f"mysql+pymysql://{mysql_user}:{encoded_password}"
        f"@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"
    )


def _get_lang_value(obj, lang, field_type="name"):
    """
    선택 언어에 맞는 값을 가져온다.

    field_type="name"이면:
      ko_name / en_name / zh_name

    field_type="des"이면:
      ko_des / en_des / zh_des
    """

    if obj is None:
        return ""

    if lang not in SUPPORTED_LANGS:
        lang = "ko"

    if field_type == "des":
        candidates = [
            f"{lang}_des",
            f"{lang}_desc",
            "ko_des",
            "ko_desc",
            "en_des",
            "en_desc",
            "zh_des",
            "zh_desc",
        ]
    else:
        candidates = [
            f"{lang}_{field_type}",
            f"ko_{field_type}",
            f"en_{field_type}",
            f"zh_{field_type}",
            field_type,
        ]

    for field_name in candidates:
        value = getattr(obj, field_name, None)

        if value is not None and str(value).strip() != "":
            return value

    return ""


def _object_to_dict(obj):
    """
    SQLAlchemy ORM 객체를 dict로 복사한다.
    원본 DB 객체의 name을 직접 바꾸면 commit 시 DB 값이 바뀔 수 있으므로 복사본을 만든다.
    """

    if obj is None:
        return {}

    if hasattr(obj, "__table__"):
        return {
            column.name: getattr(obj, column.name)
            for column in obj.__table__.columns
        }

    if hasattr(obj, "_asdict"):
        return obj._asdict()

    return {
        key: value
        for key, value in vars(obj).items()
        if not key.startswith("_")
    }


def localize_record(obj, lang=None):
    """
    Project / Category / Feature 객체를 선택 언어 기준 출력용 객체로 변환한다.

    예:
      lang == "ko" -> name = ko_name, des = ko_des
      lang == "en" -> name = en_name, des = en_des
      lang == "zh" -> name = zh_name, des = zh_des

    화면에서는 p.name, p.des만 사용하면 된다.
    """

    if obj is None:
        return None

    if lang is None:
        lang = getattr(g, "lang", "ko")

    if lang not in SUPPORTED_LANGS:
        lang = "ko"

    data = _object_to_dict(obj)

    selected_name = _get_lang_value(obj, lang, "name")
    selected_des = _get_lang_value(obj, lang, "des")

    data["raw_name"] = data.get("name", "")
    data["raw_ko_name"] = data.get("ko_name", "")
    data["raw_en_name"] = data.get("en_name", "")
    data["raw_zh_name"] = data.get("zh_name", "")

    data["raw_ko_des"] = data.get("ko_des", data.get("ko_desc", ""))
    data["raw_en_des"] = data.get("en_des", data.get("en_desc", ""))
    data["raw_zh_des"] = data.get("zh_des", data.get("zh_desc", ""))

    data["name"] = selected_name
    data["des"] = selected_des

    data["display_name"] = selected_name
    data["display_des"] = selected_des
    data["display_desc"] = selected_des

    return SimpleNamespace(**data)


def localize_records(rows, lang=None):
    """
    여러 개의 객체를 선택 언어 기준으로 변환한다.
    """

    if lang is None:
        lang = getattr(g, "lang", "ko")

    return [localize_record(row, lang) for row in rows]


def create_app():
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )

    app.secret_key = os.getenv("FLASK_SECRET_KEY", "SOME_RANDOM_SECRET")

    app.config["SQLALCHEMY_DATABASE_URI"] = _get_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    @app.before_request
    def set_current_language():
        """
        메인페이지에서 선택한 언어를 쿠키에서 읽는다.
        쿠키가 없으면 기본값은 ko.
        """
        lang = request.cookies.get("lang", "ko")

        if lang not in SUPPORTED_LANGS:
            lang = "ko"

        g.lang = lang

    from .main import bp as main_bp
    app.register_blueprint(main_bp)

    from . import eyecarex
    eyecarex.register_into(app)

    from . import handemote
    handemote.register_into(app)

    from . import musicAI
    musicAI.register_into(app)

    with app.app_context():
        print("=== URL MAP ===")
        for r in app.url_map.iter_rules():
            print(f"{r.endpoint:40s} -> {r.rule}")

        try:
            db.session.execute(text("SELECT 1"))
            print("DB ping OK")
        except Exception as e:
            print("DB ping FAILED:", e)

    def _get_current_project_path():
        path = request.path or "/"

        if path == "/":
            return None

        if path.startswith("/static"):
            return None

        if path.startswith("/favicon"):
            return None

        current_path = path.strip("/").split("/")[0]

        if not current_path:
            return None

        return current_path

    def _find_project(Project, current_path):
        if not current_path:
            return None

        current_project_url = f"/{current_path}"
        current_project_url_slash = f"/{current_path}/"

        print("=== [DEBUG] Current Project URL ===")
        print("request.path =", request.path)
        print("current_path =", current_path)
        print("current_project_url =", current_project_url)

        project_query = Project.query.filter(Project.is_active.is_(True))

        project = (
            project_query
            .filter(
                Project.url.in_([
                    current_project_url,
                    current_project_url_slash,
                    current_path,
                ])
            )
            .order_by(Project.sort_order)
            .first()
        )

        if project is None:
            project = (
                project_query
                .filter(Project.name == current_path)
                .order_by(Project.sort_order)
                .first()
            )

        return project

    def _build_sidebar_payload():
        from project.models import Project, Category, Feature

        current_path = _get_current_project_path()
        lang = getattr(g, "lang", "ko")

        if current_path is None:
            return {
                "avatar_url": None,
                "bio_text": bio_text,
                "title": "Portfolio",
                "category": [],
            }

        project = _find_project(Project, current_path)

        if project is None:
            print(f"=== [DEBUG] Project not found: {current_path} ===")
            return {
                "avatar_url": None,
                "bio_text": bio_text,
                "title": current_path or "Portfolio",
                "category": [],
            }

        localized_project = localize_record(project, lang)

        cats = (
            Category.query
            .filter_by(project_id=project.id, is_active=True)
            .order_by(Category.sort_order, Category.id)
            .all()
        )

        print("=== [DEBUG] Categories ===")

        category = []

        for c in cats:
            print(
                f"  Cat id={c.id}, "
                f"name={getattr(c, 'name', '')}, "
                f"ko={getattr(c, 'ko_name', '')}, "
                f"url={getattr(c, 'url', '')}"
            )

            localized_category = localize_record(c, lang)

            feats = (
                Feature.query
                .filter_by(category_id=c.id, is_active=True)
                .order_by(Feature.sort_order, Feature.id)
                .all()
            )

            print(f"    [DEBUG] Features in Cat {c.id} ({getattr(c, 'ko_name', '')})")

            feature_items = []

            for f in feats:
                show = getattr(f, "show", None)
                raw_url = getattr(f, "url", None)

                print(
                    f"      Feat id={f.id}, "
                    f"name={getattr(f, 'name', '')}, "
                    f"ko={getattr(f, 'ko_name', '')}, "
                    f"url={raw_url}, "
                    f"show={show}"
                )

                link = raw_url or "#"

                if show:
                    try:
                        if show == "eyecarex.eyetest.eyetest_comp.show":
                            link = url_for(
                                "eyecarex.eyetest.eyetest_comp.show",
                                disease=f.name
                            )

                        elif show.startswith("eyecarex."):
                            link = url_for(show)

                        elif show.startswith("musicAI."):
                            link = url_for(show)

                        elif show.startswith("handemote."):
                            link = url_for(show)

                        else:
                            link = show

                    except Exception as e:
                        print(f"[DEBUG] url_for failed: show={show}, error={e}")
                        link = raw_url or "#"

                if link is None or str(link).lower() == "none":
                    link = "#"

                localized_feature = localize_record(f, lang)
                localized_feature.link = link
                localized_feature.url = link

                feature_items.append(localized_feature)

            if current_path == "musicAI":
                category_link = f"#cat-{c.id}"
            else:
                category_link = c.show or c.url or "#"

            if category_link is None or str(category_link).lower() == "none":
                category_link = "#"

            category.append({
                "category_id": localized_category.id,

                "name": localized_category.name,
                "des": localized_category.des,

                "display_name": localized_category.name,
                "display_des": localized_category.des,
                "display_desc": localized_category.des,

                "url": category_link,
                "items": feature_items,

                "raw_name": localized_category.raw_name,
                "raw_ko_name": localized_category.raw_ko_name,
                "raw_en_name": localized_category.raw_en_name,
                "raw_zh_name": localized_category.raw_zh_name,
            })

        print("=== [DEBUG] category payload ===")
        for cat in category:
            print(f"  Cat {cat['category_id']} -> items={len(cat['items'])}")

        return {
            "avatar_url": localized_project.thumbnail,
            "bio_text": bio_text,
            "title": localized_project.name,
            "category": category,
        }

    @app.context_processor
    def inject_i18n():
        """
        모든 템플릿에서 사용 가능:
        {{ t('content_key') }}
        {{ current_lang }}
        """
        from project.models import Translate

        lang = getattr(g, "lang", "ko")

        try:
            rows = (
                Translate.query
                .filter_by(is_active=1)
                .all()
            )
        except Exception as e:
            print("=== [DEBUG] Translate load failed ===")
            print(e)
            rows = []

        translate_map = {}

        for row in rows:
            translate_map[row.content_key] = {
                "ko": row.ko_content,
                "en": row.en_content,
                "zh": row.zh_content,
            }

        def t(content_key):
            item = translate_map.get(content_key)

            if not item:
                return content_key

            return item.get(lang) or item.get("ko") or content_key

        return {
            "t": t,
            "current_lang": lang,
            "localize_record": localize_record,
            "localize_records": localize_records,
        }

    @app.context_processor
    def inject_header_projects():
        """
        header.html의 Projects hover 메뉴에서 사용할 프로젝트 리스트.
        모든 페이지에서 header_projects 사용 가능.
        """
        from project.models import Project

        lang = getattr(g, "lang", "ko")

        try:
            project_rows = (
                Project.query
                .filter(Project.is_active.is_(True))
                .order_by(Project.sort_order, Project.id)
                .all()
            )
        except Exception as e:
            print("=== [DEBUG] Header projects load failed ===")
            print(e)
            project_rows = []

        header_projects = []

        for project in project_rows:
            localized_project = localize_record(project, lang)

            project_url = getattr(localized_project, "url", None)

            if (
                project_url is None
                or str(project_url).strip() == ""
                or str(project_url).lower() == "none"
            ):
                project_url = "/project"

            header_projects.append({
                "id": localized_project.id,
                "display_name": localized_project.display_name or localized_project.name or "Project",
                "url": project_url,
            })

        return {
            "header_projects": header_projects
        }

    @app.context_processor
    def inject_sidebar_payload():
        try:
            return _build_sidebar_payload()
        except Exception as e:
            print("=== [DEBUG] Sidebar payload failed ===")
            print(e)

            return {
                "avatar_url": None,
                "bio_text": bio_text,
                "title": "Portfolio",
                "category": [],
            }

    return app