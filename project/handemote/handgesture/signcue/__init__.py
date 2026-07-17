from flask import Blueprint

bp = Blueprint(
    "signcue",
    __name__,
    url_prefix="/signcue",
    template_folder="templates",
    static_folder="static",
)

# service_signcue.py 안의 show, cam 라우트를 등록한다.
from . import service_signcue  # noqa: E402, F401


def register_into(parent_bp):
    parent_bp.register_blueprint(bp)