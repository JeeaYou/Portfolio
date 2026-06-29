# project/main.py
from datetime import datetime
from io import BytesIO

from flask import (
    Blueprint,
    render_template,
    g,
    request,
    jsonify,
    send_file,
    current_app,
)

from project import db, localize_records
from project.models import Project, ArchiveItem, Resume

import os
import smtplib
from email.message import EmailMessage

from weasyprint import HTML, CSS

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    lang = getattr(g, "lang", "ko")

    rows = (
        Project.query
        .filter_by(is_active=1)
        .order_by(Project.sort_order.asc())
        .all()
    )

    projects = localize_records(rows, lang)

    return render_template(
        "mainpage.html",
        projects=projects,
        show_sidebar=False,
    )


@bp.get("/about")
def about():
    return render_template(
        "about.html",
        show_sidebar=False,
    )


@bp.get("/skills")
def skills():
    return render_template(
        "skills.html",
        show_sidebar=False,
    )


@bp.get("/archive")
def archive():
    lang = getattr(g, "lang", "ko")

    archive_items = (
        ArchiveItem.query
        .filter_by(is_active=True)
        .order_by(
            ArchiveItem.archive_date.desc(),
            ArchiveItem.featured.desc(),
            ArchiveItem.sort_order.asc()
        )
        .all()
    )

    return render_template(
        "archive.html",
        archive_items=archive_items,
        current_lang=lang,
        show_sidebar=False,
    )


def get_resume_content(row, lang):
    if lang == "ko":
        return row.ko_content or row.en_content or ""
    if lang == "zh":
        return row.zh_content or row.en_content or ""
    return row.en_content or ""


@bp.get("/resume")
def resume():
    lang = getattr(g, "lang", "ko")
    current_lang = lang

    rows = (
        Resume.query
        .filter_by(is_active=True)
        .order_by(Resume.sort_order.asc())
        .all()
    )

    resume_map = {}

    for row in rows:
        resume_map[row.content_key] = {
            "id": row.id,
            "section_key": row.section_key,
            "content_key": row.content_key,
            "parent_key": row.parent_key,
            "item_type": row.item_type,
            "icon": row.icon,
            "link_url": row.link_url,
            "content": get_resume_content(row, current_lang),
            "sort_order": row.sort_order,
            "is_editable": row.is_editable,
            "is_print_visible": row.is_print_visible,
        }

    skills = [
        {
            "label_key": "skill_languages_label",
            "value_key": "skill_languages_value",
            "label": resume_map.get("skill_languages_label", {}).get("content", ""),
            "value": resume_map.get("skill_languages_value", {}).get("content", ""),
        },
        {
            "label_key": "skill_frameworks_label",
            "value_key": "skill_frameworks_value",
            "label": resume_map.get("skill_frameworks_label", {}).get("content", ""),
            "value": resume_map.get("skill_frameworks_value", {}).get("content", ""),
        },
        {
            "label_key": "skill_web_api_label",
            "value_key": "skill_web_api_value",
            "label": resume_map.get("skill_web_api_label", {}).get("content", ""),
            "value": resume_map.get("skill_web_api_value", {}).get("content", ""),
        },
        {
            "label_key": "skill_database_label",
            "value_key": "skill_database_value",
            "label": resume_map.get("skill_database_label", {}).get("content", ""),
            "value": resume_map.get("skill_database_value", {}).get("content", ""),
        },
        {
            "label_key": "skill_ai_label",
            "value_key": "skill_ai_value",
            "label": resume_map.get("skill_ai_label", {}).get("content", ""),
            "value": resume_map.get("skill_ai_value", {}).get("content", ""),
        },
        {
            "label_key": "skill_other_label",
            "value_key": "skill_other_value",
            "label": resume_map.get("skill_other_label", {}).get("content", ""),
            "value": resume_map.get("skill_other_value", {}).get("content", ""),
        },
    ]

    projects = [
        {
            "label_key": "project_musicai_label",
            "value_key": "project_musicai_value",
            "label": resume_map.get("project_musicai_label", {}).get("content", ""),
            "value": resume_map.get("project_musicai_value", {}).get("content", ""),
        },
        {
            "label_key": "project_eyecarex_label",
            "value_key": "project_eyecarex_value",
            "label": resume_map.get("project_eyecarex_label", {}).get("content", ""),
            "value": resume_map.get("project_eyecarex_value", {}).get("content", ""),
        },
        {
            "label_key": "project_handemote_label",
            "value_key": "project_handemote_value",
            "label": resume_map.get("project_handemote_label", {}).get("content", ""),
            "value": resume_map.get("project_handemote_value", {}).get("content", ""),
        },
    ]

    languages = [
        {
            "label_key": "lang_korean_label",
            "value_key": "lang_korean_value",
            "label": resume_map.get("lang_korean_label", {}).get("content", ""),
            "value": resume_map.get("lang_korean_value", {}).get("content", ""),
        },
        {
            "label_key": "lang_chinese_label",
            "value_key": "lang_chinese_value",
            "label": resume_map.get("lang_chinese_label", {}).get("content", ""),
            "value": resume_map.get("lang_chinese_value", {}).get("content", ""),
        },
        {
            "label_key": "lang_english_label",
            "value_key": "lang_english_value",
            "label": resume_map.get("lang_english_label", {}).get("content", ""),
            "value": resume_map.get("lang_english_value", {}).get("content", ""),
        },
    ]

    certifications = [
        {
            "key": "cert_sqld",
            "content": resume_map.get("cert_sqld", {}).get("content", ""),
        },
        {
            "key": "cert_ipe",
            "content": resume_map.get("cert_ipe", {}).get("content", ""),
        },
        {
            "key": "cert_brity",
            "content": resume_map.get("cert_brity", {}).get("content", ""),
        },
    ]

    return render_template(
        "resume.html",
        resume_map=resume_map,
        skills=skills,
        projects=projects,
        languages=languages,
        certifications=certifications,
        current_lang=current_lang,
        show_sidebar=False,
    )


@bp.post("/resume/update")
def update_resume():
    """
    resume.js에서 보내는 데이터 형식:

    {
      "lang": "ko",
      "items": [
        {
          "content_key": "resume_name",
          "content": "JEEA YOU"
        }
      ]
    }
    """

    data = request.get_json(silent=True) or {}

    lang = data.get("lang") or getattr(g, "lang", "ko")
    items = data.get("items", [])

    if lang not in ["ko", "en", "zh"]:
        lang = "ko"

    if not isinstance(items, list) or len(items) == 0:
        return jsonify({
            "success": False,
            "message": "저장할 이력서 데이터가 없습니다."
        }), 400

    column_map = {
        "ko": "ko_content",
        "en": "en_content",
        "zh": "zh_content",
    }

    update_column = column_map[lang]

    updated_count = 0
    skipped_keys = []

    try:
        for item in items:
            content_key = str(item.get("content_key", "")).strip()
            content = item.get("content", "")

            if not content_key:
                continue

            if content is None:
                content = ""

            row = (
                Resume.query
                .filter_by(
                    content_key=content_key,
                    is_active=True
                )
                .first()
            )

            if row is None:
                skipped_keys.append(content_key)
                continue

            if row.is_editable is False:
                skipped_keys.append(content_key)
                continue

            setattr(row, update_column, content)
            row.updated_at = datetime.now()

            updated_count += 1

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"{updated_count}개 항목이 저장되었습니다.",
            "updated_count": updated_count,
            "skipped_keys": skipped_keys,
            "lang": lang,
        })

    except Exception as e:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": f"DB 저장 중 오류가 발생했습니다: {str(e)}"
        }), 500
    

@bp.post("/resume/send")
def send_resume():
    data = request.get_json(silent=True) or {}

    recipient_email = str(data.get("email", "")).strip()
    lang = data.get("lang") or getattr(g, "lang", "ko")
    resume_html = data.get("resume_html", "")

    if not recipient_email:
        return jsonify({
            "success": False,
            "message": "받는 사람 이메일 주소가 없습니다."
        }), 400

    if not resume_html:
        return jsonify({
            "success": False,
            "message": "이력서 HTML 데이터가 없습니다."
        }), 400

    try:
        from weasyprint import HTML
    except Exception as e:
        return jsonify({
            "success": False,
            "message": (
                "WeasyPrint 실행에 필요한 macOS 라이브러리를 찾지 못했습니다. "
                "터미널에서 'brew install weasyprint' 또는 "
                "'brew install glib pango cairo gdk-pixbuf libffi'를 실행한 뒤 "
                "DYLD_FALLBACK_LIBRARY_PATH를 설정해주세요. "
                f"원인: {str(e)}"
            )
        }), 500

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    mail_from = os.getenv("MAIL_FROM") or smtp_user

    print("SMTP_USER =", smtp_user)
    print("SMTP_PASSWORD exists =", bool(smtp_password))
    print("SMTP_PASSWORD length =", len(smtp_password or ""))
    print("MAIL_FROM =", mail_from)

    if not smtp_user or not smtp_password or not mail_from:
        return jsonify({
            "success": False,
            "message": "SMTP 설정이 없습니다. .env의 SMTP_USER, SMTP_PASSWORD, MAIL_FROM을 확인해주세요."
        }), 500

    try:
        css_url = request.host_url.rstrip("/") + "/static/assets/css/resume.css"

        full_html = f"""
        <!doctype html>
        <html lang="{lang}">
        <head>
            <meta charset="utf-8">
            <link rel="stylesheet" href="{css_url}">
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background: #ffffff;
                }}

                .no-print {{
                    display: none !important;
                }}

                .resume-paper {{
                    box-shadow: none !important;
                    margin: 0 auto !important;
                }}
            </style>
        </head>
        <body>
            {resume_html}
        </body>
        </html>
        """

        pdf_bytes = HTML(
            string=full_html,
            base_url=request.host_url
        ).write_pdf()

        subject_map = {
            "ko": "이력서 전달드립니다",
            "en": "Resume Submission",
            "zh": "简历发送"
        }

        body_map = {
            "ko": "안녕하세요.\n\n이력서를 PDF 파일로 첨부드립니다.\n\n감사합니다.",
            "en": "Hello,\n\nPlease find my resume attached as a PDF file.\n\nThank you.",
            "zh": "您好，\n\n附件中是我的简历 PDF 文件。\n\n谢谢。"
        }

        subject = subject_map.get(lang, subject_map["en"])
        body = body_map.get(lang, body_map["en"])

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = mail_from
        message["To"] = recipient_email
        message.set_content(body)

        message.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename="Jeea_You_Resume.pdf"
        )

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(message)

        return jsonify({
            "success": True,
            "message": "이력서가 이메일로 발송되었습니다."
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"메일 발송 중 오류가 발생했습니다: {str(e)}"
        }), 500
    

@bp.post("/resume/download")
def download_resume_pdf():
    try:
        data = request.get_json(silent=True) or {}

        resume_html = data.get("resume_html", "")
        lang = data.get("lang", "ko")

        if not resume_html:
            return jsonify({
                "success": False,
                "message": "PDF로 변환할 이력서 HTML이 없습니다."
            }), 400

        css_path = os.path.join(
            current_app.root_path,
            "static",
            "assets",
            "css",
            "resume.css"
        )

        full_html = f"""
        <!DOCTYPE html>
        <html lang="{lang}">
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: A4;
                    margin: 12mm;
                }}

                body {{
                    margin: 0;
                    padding: 0;
                    background: #ffffff;
                }}

                .no-print {{
                    display: none !important;
                }}

                .resume-paper {{
                    box-shadow: none !important;
                    margin: 0 auto !important;
                }}
            </style>
        </head>
        <body>
            {resume_html}
        </body>
        </html>
        """

        pdf_bytes = HTML(
            string=full_html,
            base_url=request.url_root
        ).write_pdf(
            stylesheets=[
                CSS(filename=css_path)
            ]
        )

        pdf_file = BytesIO(pdf_bytes)
        pdf_file.seek(0)

        return send_file(
            pdf_file,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="JeeaYou_Resume.pdf"
        )

    except Exception as e:
        import traceback

        print("=== RESUME PDF DOWNLOAD ERROR ===")
        print(repr(e))
        traceback.print_exc()

        return jsonify({
            "success": False,
            "message": f"PDF 생성 중 오류가 발생했습니다: {str(e)}"
        }), 500