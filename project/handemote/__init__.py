# project/handemote/__init__.py
from flask import Blueprint, render_template, url_for
from sqlalchemy import func
from project import db
from project.models import Project, Category, Feature
from sqlalchemy.orm import load_only


bp = Blueprint(
    "handemote", __name__,
    url_prefix="/handemote",
    template_folder="templates",
    static_folder="static",
)

@bp.get("/", endpoint="handemote")
def handemote():
    # 개별 페이지는 이제 사이드바 데이터를 따로 넘길 필요 없음
    # 페이지 전용 데이터만 추가해서 렌더링
    return render_template("handemote.html")

def register_into(app):
    # ✅ 1) 먼저 자식 트리(eyetest, game)를 handemote(bp)에 부착
    from .handgesture import register_into as register_eyetest
    register_eyetest(bp)   # -> /handemote/eyetest/...
    
    # from .game    import register_into as register_game
    # register_game(bp)      # -> /handemote/game/...

    # ✅ 2) 완성된 eyecarex를 앱에 '한 번만' 등록
    app.register_blueprint(bp)
