# views/eyetest/colortest/__init__.py
from flask import Blueprint

bp = Blueprint(
    "colortest", __name__,
    url_prefix="/colortest",
    template_folder="templates", 
    static_folder="static"
    )
from . import service_colortest  # noqa
