# project/eyecarex/game/__init__.py
from flask import Blueprint, render_template

bp = Blueprint(
    "winkbird", __name__,
    url_prefix="/winkbird",
    template_folder="templates",
    static_folder="static",
)
from . import service_winkbird  # noqa
