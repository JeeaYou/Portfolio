from flask import Blueprint, render_template

bp = Blueprint("contact", __name__, url_prefix='/')

@bp.route("/contact")
def index():
    return render_template("contact.html")


