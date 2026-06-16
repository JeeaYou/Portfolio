from flask import Flask, url_for, request
import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import load_only   # ✅ 여기서 import

db = SQLAlchemy()

def create_app():
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )
    app.secret_key = "SOME_RANDOM_SECRET"
    
     # MySQL 연결문자열 (로컬 MySQL 예시)
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "mysql+pymysql://root:1q2w3e4r!@127.0.0.1:3306/project?charset=utf8mb4"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

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
            
        # DB 연결만 간단 체크 (부작용 없음)
        try:
            db.session.execute(db.text("SELECT 1"))
            print("DB ping OK")
        except Exception as e:
            print("DB ping FAILED:", e)
    def _build_sidebar_payload():
        from project.models import Project, Category, Feature

        current_path = request.path.strip("/").split("/")[0]
        current_project_url = f"/{current_path}" if current_path else "/"

        print("=== [DEBUG] Current Project URL ===")
        print("request.path =", request.path)
        print("current_project_url =", current_project_url)

        project = (
            Project.query.options(
                load_only(
                    Project.id,
                    Project.name,
                    Project.sort_order,
                    Project.en_name,
                    Project.ko_name,
                    Project.zh_name,
                    Project.url,
                    Project.thumbnail,
                    Project.is_active,
                )
            )
            .filter(
                Project.is_active.is_(True),
                Project.url == current_project_url
            )
            .order_by(Project.sort_order)
            .first()
        )

        if project is None:
            project = (
                Project.query.options(
                    load_only(
                        Project.id,
                        Project.name,
                        Project.sort_order,
                        Project.en_name,
                        Project.ko_name,
                        Project.zh_name,
                        Project.url,
                        Project.thumbnail,
                        Project.is_active,
                    )
                )
                .filter(
                    Project.is_active.is_(True),
                    Project.name == current_path
                )
                .order_by(Project.sort_order)
                .first()
            )

        if project is None:
            print("=== [DEBUG] Project not found ===")
            return {
                "avatar_url": None,
                "bio_text": "배움은 끝이 없다!",
                "title": current_path or "Portfolio",
                "category": [],
            }

        cats = (
            Category.query.options(
                load_only(
                    Category.id,
                    Category.name,
                    Category.sort_order,
                    Category.en_name,
                    Category.ko_name,
                    Category.zh_name,
                    Category.url,
                    Category.show,
                    Category.en_des,
                    Category.ko_des,
                    Category.zh_des,
                    Category.is_active,
                )
            )
            .filter_by(project_id=project.id, is_active=True)
            .order_by(Category.sort_order, Category.id)
            .all()
        )

        print("=== [DEBUG] Categories ===")

        category = []

        for c in cats:
            print(f"  Cat id={c.id}, name={c.name}, ko={c.ko_name}, url={c.url}")

            feats = (
                Feature.query.options(
                    load_only(
                        Feature.id,
                        Feature.name,
                        Feature.sort_order,
                        Feature.en_name,
                        Feature.ko_name,
                        Feature.zh_name,
                        Feature.url,
                        Feature.en_des,
                        Feature.ko_des,
                        Feature.zh_des,
                        Feature.thumbnail,
                        Feature.show,
                        Feature.is_active,
                    )
                )
                .filter_by(category_id=c.id, is_active=True)
                .order_by(Feature.sort_order, Feature.id)
                .all()
            )

            print(f"    [DEBUG] Features in Cat {c.id} ({c.ko_name})")

            for f in feats:
                show = f.show
                raw_url = f.url

                print(
                    f"      Feat id={f.id}, name={f.name}, "
                    f"ko={f.ko_name}, url={f.url}, show={f.show}"
                )

                link = raw_url or "#"

                if show:
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

                if link is None or str(link).lower() == "none":
                    link = "#"

                f.link = link

            # musicAI 페이지에서는 카테고리 클릭 시 페이지 이동이 아니라 섹션 이동
            if current_path == "musicAI":
                category_link = f"#cat-{c.id}"
            else:
                category_link = c.show or c.url or "#"

            if category_link is None or str(category_link).lower() == "none":
                category_link = "#"

            category.append({
                "category_id": c.id,
                "name": c.name,
                "en_name": c.en_name,
                "ko_name": c.ko_name,
                "zh_name": c.zh_name,

                # 기존 템플릿 호환용
                "desc": c.ko_des or "",

                # musicAI.html에서 cat.ko_desc 쓰고 있어서 필요
                "en_desc": c.en_des or "",
                "ko_desc": c.ko_des or "",
                "zh_desc": c.zh_des or "",

                "url": category_link,
                "items": feats,
            })

        print("=== [DEBUG] category payload ===")
        for cat in category:
            print(f"  Cat {cat['category_id']} -> items={len(cat['items'])}")

        return {
            "avatar_url": project.thumbnail,
            "bio_text": "배움은 끝이 없다!",
            "title": project.ko_name,
            "category": category,
        }

    @app.context_processor
    def inject_sidebar_for_eyecarex():
        """이 블루프린트에서 렌더링되는 모든 템플릿에 사이드바 데이터 주입"""
        try:
            return _build_sidebar_payload()
        except Exception:
            # 실패 시 최소 구조라도 리턴 (페이지 자체는 뜨게)
            return {
                "avatar_url": None,
                "bio_text": "배움은 끝이 없다!",
                "title": "eyecarex",
                "category": [],
            }

    return app
