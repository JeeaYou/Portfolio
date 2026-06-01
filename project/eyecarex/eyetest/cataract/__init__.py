# project/eyecarex/eyetest/cataract/__init__.py
from flask import Blueprint

bp = Blueprint(
    "cataract", __name__,
    url_prefix="/cataract",
    template_folder="templates", 
    static_folder="static"
    )

from . import service_cataract  # noqa


