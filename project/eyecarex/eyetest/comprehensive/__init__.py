# project/eyecarex/eyetest/comprehensive/__init__.py
from flask import Blueprint

bp = Blueprint(
    "eyetest_comp", __name__,                 # ← 고유한 이름
    url_prefix="/eyetest_comp",               # ← 최종 URL prefix
    template_folder="templates",
    static_folder="static",
)
from . import service_comprehensive  # noqa

