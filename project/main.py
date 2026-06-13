# project/main.py
from flask import Blueprint, render_template
from project.models import Project

bp = Blueprint("main", __name__)

@bp.get("/")
def index():
    # SELECT id, ko_name, en_name, url FROM projects WHERE is_active=1
    rows = (
        Project.query.with_entities(
            Project.id, Project.ko_name, Project.en_name, Project.url
        )
        .filter_by(is_active=1)
        .order_by(Project.sort_order.asc())
        .all()
    )

    # ✅ index.html에서는 사이드바 사용 안 함
    return render_template(
        "index.html",
        projects=rows,
        show_sidebar=False,
    )
