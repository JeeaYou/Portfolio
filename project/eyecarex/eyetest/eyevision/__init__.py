# project/eyecarex/eyetest/eyevision/__init__.py
from flask import Blueprint

bp = Blueprint(
    "eyevision", __name__,       # endpoint prefix: eyecarex.eyetest.eyevision.*
    url_prefix="/eyevision",
    template_folder="templates",
    static_folder="static",
)

from . import service_eyevision  # ← 여기서 라우트만 붙입니다 (중요)
