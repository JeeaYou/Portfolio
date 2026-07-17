# project/handemote/handgesture/signcue/service_eyevision.py
from flask import Blueprint, render_template, request, Response, current_app, url_for, redirect
from . import bp  # ← __init__.py의 bp를 가져옴 (중요)

@bp.get("/", endpoint="show")  # 최종 이름: handgesture.signcue.show
def show():
    return render_template("signcue.html")