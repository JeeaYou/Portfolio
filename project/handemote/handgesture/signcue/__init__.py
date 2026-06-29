from flask import Blueprint, render_template

bp = Blueprint(
    "signcue",
    __name__,
    url_prefix="/signcue",
    template_folder="templates",
    static_folder="static",
)


@bp.get("/", endpoint="show")
def show():
    return render_template("signcue.html")


def register_into(parent_bp):
    parent_bp.register_blueprint(bp)