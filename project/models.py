from sqlalchemy import text
from . import db


class Project(db.Model):
    __tablename__ = "projects"

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    en_name    = db.Column(db.String(100), nullable=False)
    ko_name    = db.Column(db.String(100), nullable=False)
    zh_name    = db.Column(db.String(100), nullable=False)

    url        = db.Column(db.String(128))
    thumbnail  = db.Column(db.String(255))
    is_active  = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = db.Column(
        db.TIMESTAMP, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class Category(db.Model):
    __tablename__ = "category"

    id         = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    name       = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    en_name    = db.Column(db.String(100), nullable=False)
    ko_name    = db.Column(db.String(100), nullable=False)
    zh_name    = db.Column(db.String(100), nullable=False)

    url        = db.Column(db.String(128))
    en_des     = db.Column(db.String(255))
    ko_des     = db.Column(db.String(255))
    zh_des     = db.Column(db.String(255))

    show  = db.Column(db.String(255))
    is_active  = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = db.Column(
        db.TIMESTAMP, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class Feature(db.Model):
    __tablename__ = "features"

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    name        = db.Column(db.String(100), nullable=False)
    sort_order  = db.Column(db.Integer, default=0)

    en_name     = db.Column(db.String(100), nullable=False)
    ko_name     = db.Column(db.String(100), nullable=False)
    zh_name     = db.Column(db.String(100), nullable=False)

    url         = db.Column(db.String(128))
    en_des      = db.Column(db.String(255))
    ko_des      = db.Column(db.String(255))
    zh_des      = db.Column(db.String(255))

    thumbnail   = db.Column(db.String(255))
    show   = db.Column(db.String(255))
    cam   = db.Column(db.Boolean, nullable=False, default=True)
    is_active   = db.Column(db.Boolean, nullable=False, default=True)

    created_at  = db.Column(
        db.TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at  = db.Column(
        db.TIMESTAMP, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
