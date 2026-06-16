# views/contact/__init__.py
from flask import Blueprint
bp = Blueprint("contact", __name__,
               url_prefix="/contact",
               template_folder="templates", static_folder="static")
from . import routes  # noqa


