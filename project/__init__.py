from flask import Flask, url_for
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
        
        # 1) 프로젝트 찾기 (url='/eyecarex')
        project = (
            Project.query.options(
                load_only(
                    Project.id,
                    Project.name,
                    Project.ko_name,
                    Project.en_name,
                    Project.zh_name,
                    Project.url,
                    Project.thumbnail,
                    Project.is_active,
                )
            )
            .filter(Project.is_active.is_(True),)
            .order_by(Project.id)   # sort_order는 없음 -> id로 정렬
            .first_or_404())
        print("=== [DEBUG] Project ===")
        print(f"id={project.id}, name={project.name}, ko={project.ko_name}, url={project.url}")

    # 하위 카테고리 불러오기
        cats = (Category
                .query.options(
                    load_only(
                        Category.id, 
                        Category.name,
                        Category.ko_name,
                        Category.en_name, 
                        Category.zh_name,
                        Category.url, 
                        Category.sort_order, 
                        Category.show, 
                        Category.des, 
                        Category.is_active
                        )
                    )
                .filter_by(project_id = project.id, is_active=True)
                .order_by(Category.sort_order, Category.id)
                .all())
        
        print("=== [DEBUG] Categories ===")
        category = []
        for c in cats:
            print(f"  Cat id={c.id}, name={c.name}, ko={c.ko_name}, url={c.url}")
            feats = (
                Feature.query.options(
                    load_only(
                        Feature.id,
                        Feature.name,
                        Feature.ko_name, 
                        Feature.en_name, 
                        Feature.zh_name,
                        Feature.url, 
                        Feature.sort_order,
                        Feature.thumbnail, 
                        Feature.show, 
                        Feature.is_active
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
                print(f"      Feat id={f.id}, name={f.name}, ko={f.ko_name}, url={f.url}, show={f.show}")

                # 링크 계산 (BuildError 회피)
                link = raw_url or "#"
                if show:
                    if show == "eyecarex.eyetest.eyetest_comp.show":
                        link = url_for("eyecarex.eyetest.eyetest_comp.show", disease=f.name)

                    elif "eyecarex." in show:
                        link = url_for(show)

                    else:
                        link = show
                f.link = link

            category.append({
                "category_id": c.id,          # ← 이 줄 추가
                "ko_name": c.ko_name,
                "desc": c.des or "",
                "url": c.show,
                "items": feats,  # 템플릿에서 item.link / item.thumbnail 사용
            })
            
        print("=== [DEBUG] category payload ===")
        for cat in category:
            print(f"  Cat {cat['category_id']} -> items={len(cat['items'])}")

        return {
            "avatar_url" : project.thumbnail,
            "bio_text" : "배움은 끝이 없다!",
            "title" : project.ko_name,
            "category" : category,
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
