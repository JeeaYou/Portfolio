# views/contact/routes.py
from . import bp
from flask import render_template
@bp.get("/", strict_slashes=False)
def page():
    return render_template("contact.html")  # 이 블루프린트의 templates 기준