from flask import Blueprint, render_template

bp = Blueprint(
    "eyetest", __name__,
    url_prefix="/eyetest",
    template_folder="templates",
    static_folder="static",
)

@bp.get("/", endpoint="index")  # 또는 endpoint="index"
def eyetest():
    return render_template("eyetest.html")

def register_into(parent_bp):
    # ✅ 손자 BP들을 먼저 eyetest(bp)에 부착
    from .eyevision     import bp as eyevision_bp
    from .colortest     import bp as colortest_bp
    from .cataract      import bp as cataract_bp
    from .comprehensive import bp as comprehensive_bp

    bp.register_blueprint(eyevision_bp)      # /eyecarex/eyetest/eyevision
    bp.register_blueprint(colortest_bp)      # /eyecarex/eyetest/colortest
    bp.register_blueprint(cataract_bp)       # /eyecarex/eyetest/cataract
    bp.register_blueprint(comprehensive_bp)  # /eyecarex/eyetest/comprehensive

    # ✅ 그 다음에 eyetest를 부모(eyecarex)에 '한 번' 부착
    parent_bp.register_blueprint(bp)
