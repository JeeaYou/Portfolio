from flask import Blueprint, render_template

bp = Blueprint(
    "handgesture", __name__,
    url_prefix="/handgesture",
    template_folder="templates",
    static_folder="static",
)

@bp.get("/", endpoint="index")  # 또는 endpoint="index"
def handgesture():
    return render_template("handgesture.html")

def register_into(parent_bp):
    # ✅ 손자 BP들을 먼저 handgesture(bp)에 부착
    from .signcue     import bp as signcue_bp


    bp.register_blueprint(signcue_bp)


    # ✅ 그 다음에 handgesture를 부모(eyecarex)에 '한 번' 부착
    parent_bp.register_blueprint(bp)
