# project/eyecarex/game/__init__.py
from flask import Blueprint, render_template


bp = Blueprint(
    "game", __name__,
    url_prefix="/game",
    template_folder="templates",
    static_folder="static",
)
@bp.get("/", endpoint="index")
def game():
    return render_template("game.html")

def register_into(parent_bp):
    # 손자부터 부착
    from .winkbird import bp as winkbird_bp
    bp.register_blueprint(winkbird_bp)     # /eyecarex/game/winkbird

    # 그 다음 부모(eyecarex)에 부착
    parent_bp.register_blueprint(bp)

