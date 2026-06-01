# project/eyecarex/__init__.py
from flask import Blueprint, render_template, url_for
from sqlalchemy import func
from project import db
from project.models import Project, Category, Feature
from sqlalchemy.orm import load_only


bp = Blueprint(
    "eyecarex", __name__,
    url_prefix="/eyecarex",
    template_folder="templates",
    static_folder="static",
)

@bp.get("/", endpoint="eyecarex")
def eyecarex():
    # 개별 페이지는 이제 사이드바 데이터를 따로 넘길 필요 없음
    # 페이지 전용 데이터만 추가해서 렌더링
    return render_template("eyecarex.html")

def register_into(app):
    # ✅ 1) 먼저 자식 트리(eyetest, game)를 eyecarex(bp)에 부착
    from .eyetest import register_into as register_eyetest
    from .game    import register_into as register_game
    register_eyetest(bp)   # -> /eyecarex/eyetest/...
    register_game(bp)      # -> /eyecarex/game/...

    # ✅ 2) 완성된 eyecarex를 앱에 '한 번만' 등록
    app.register_blueprint(bp)
