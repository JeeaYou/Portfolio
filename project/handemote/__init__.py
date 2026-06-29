from flask import Blueprint, render_template

bp = Blueprint(
    "handemote",
    __name__,
    url_prefix="/handemote",
    template_folder="templates",
    static_folder="static",
)


@bp.get("/", endpoint="handemote")
def handemote():
    return render_template("handemote.html")


def register_into(app):
    from .handgesture.signcue import register_into as register_signcue
    register_signcue(bp)

    app.register_blueprint(bp)