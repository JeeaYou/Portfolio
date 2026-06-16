# project/handemote/handgesture/signcue/__init__.py
from flask import Blueprint

bp = Blueprint(
    "signcue", __name__,       # endpoint prefix: handemote.handgesture.signcue.*
    url_prefix="/signcue",
    template_folder="templates",
    static_folder="static",
)

from . import service_signcue  # ← 여기서 라우트만 붙입니다 (중요)
