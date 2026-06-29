from sqlalchemy import text
from . import db


class Translate(db.Model):
    __tablename__ = "translate"

    id = db.Column(db.Integer, primary_key=True)

    page_name = db.Column(db.String(100))
    page = db.Column(db.String(100))
    pre_tag = db.Column(db.String(100))

    tag_type = db.Column(db.String(50))
    class_name = db.Column(db.String(100))
    id_name = db.Column(db.String(100))

    content_key = db.Column(db.String(150), nullable=False, unique=True)

    en_content = db.Column(db.Text)
    ko_content = db.Column(db.Text)
    zh_content = db.Column(db.Text)

    updated_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    en_name = db.Column(db.String(100), nullable=False)
    ko_name = db.Column(db.String(100), nullable=False)
    zh_name = db.Column(db.String(100), nullable=False)

    en_des = db.Column(db.String(255))
    ko_des = db.Column(db.String(255))
    zh_des = db.Column(db.String(255))

    url = db.Column(db.String(128))
    thumbnail = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    updated_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class Category(db.Model):
    __tablename__ = "category"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    en_name = db.Column(db.String(100), nullable=False)
    ko_name = db.Column(db.String(100), nullable=False)
    zh_name = db.Column(db.String(100), nullable=False)

    url = db.Column(db.String(128))

    en_des = db.Column(db.String(255))
    ko_des = db.Column(db.String(255))
    zh_des = db.Column(db.String(255))

    show = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    updated_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class Feature(db.Model):
    __tablename__ = "features"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    en_name = db.Column(db.String(100), nullable=False)
    ko_name = db.Column(db.String(100), nullable=False)
    zh_name = db.Column(db.String(100), nullable=False)

    url = db.Column(db.String(128))

    en_des = db.Column(db.String(255))
    ko_des = db.Column(db.String(255))
    zh_des = db.Column(db.String(255))

    thumbnail = db.Column(db.String(255))
    show = db.Column(db.String(255))
    cam = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    updated_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class MusicTrack(db.Model):
    __tablename__ = "music_tracks"

    track_id = db.Column(db.String(50), primary_key=True)
    file_name = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.Text, nullable=False)
    duration = db.Column(db.Numeric(10, 2))
    is_active = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )


class MusicAudioFeature(db.Model):
    __tablename__ = "audio_features"

    audio_feature_id = db.Column(db.String(50), primary_key=True)

    track_id = db.Column(
        db.String(50),
        db.ForeignKey("music_tracks.track_id"),
        nullable=False
    )

    music_key = db.Column(db.String(50))
    tempo = db.Column(db.Numeric(6, 2))
    rhythm_patterns = db.Column(db.Text)
    pitch_class_profiles = db.Column(db.String(50))
    min_pitch = db.Column(db.String(20))
    max_pitch = db.Column(db.String(20))
    pitch_range = db.Column(db.String(50))
    genre = db.Column(db.String(100))
    instrument_types = db.Column(db.Text)
    energy = db.Column(db.Numeric(5, 2))
    danceability = db.Column(db.Numeric(5, 2))
    mood = db.Column(db.String(100))
    spectral_centroid = db.Column(db.Numeric(10, 2))
    spectral_flux = db.Column(db.Numeric(10, 4))
    dynamic_range = db.Column(db.Numeric(10, 2))
    harmonic_to_noise_ratio = db.Column(db.Numeric(10, 4))

    zero_crossing_rate = db.Column(db.Numeric(10, 6))
    spectral_bandwidth = db.Column(db.Numeric(10, 2))
    spectral_rolloff = db.Column(db.Numeric(10, 2))
    spectral_flatness = db.Column(db.Numeric(10, 6))

    mfcc_mean = db.Column(db.Text)
    mfcc_std = db.Column(db.Text)
    spectral_contrast_mean = db.Column(db.Text)
    chroma_mean = db.Column(db.Text)
    tonnetz_mean = db.Column(db.Text)

    is_active = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )


class MusicCluster(db.Model):
    __tablename__ = "music_clusters"

    cluster_result_id = db.Column(db.String(50), primary_key=True)

    track_id = db.Column(
        db.String(50),
        db.ForeignKey("music_tracks.track_id"),
        nullable=False
    )

    cluster_id = db.Column(db.Integer, nullable=False)
    group_label = db.Column(db.String(50))
    is_active = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )


class AnalysisJob(db.Model):
    __tablename__ = "analysis_jobs"

    request_job_id = db.Column(db.String(50), primary_key=True)

    track_id = db.Column(
        db.String(50),
        db.ForeignKey("music_tracks.track_id"),
        nullable=True
    )

    status = db.Column(db.String(50), nullable=False)
    error_message = db.Column(db.Text)
    started_at = db.Column(db.TIMESTAMP)
    finished_at = db.Column(db.TIMESTAMP)
    is_active = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

class ArchiveItem(db.Model):
    __tablename__ = "archive_items"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    project_name = db.Column(db.String(100), nullable=False)
    category_key = db.Column(db.String(50), nullable=False)

    ko_category = db.Column(db.String(100))
    en_category = db.Column(db.String(100))
    zh_category = db.Column(db.String(100))

    ko_title = db.Column(db.String(255))
    en_title = db.Column(db.String(255))
    zh_title = db.Column(db.String(255))

    ko_description = db.Column(db.Text)
    en_description = db.Column(db.Text)
    zh_description = db.Column(db.Text)

    tech_stack = db.Column(db.String(500))

    status = db.Column(db.String(50), default="Completed")
    visual = db.Column(db.String(50), default="code")
    archive_date = db.Column(db.Date)

    sort_order = db.Column(db.Integer, default=0)
    featured = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)


class Resume(db.Model):
    __tablename__ = "resume"

    id = db.Column(db.BigInteger, primary_key=True)

    section_key = db.Column(db.String(50), nullable=False)
    content_key = db.Column(db.String(100), nullable=False, unique=True)

    parent_key = db.Column(db.String(100))
    item_type = db.Column(db.String(30), nullable=False)

    icon = db.Column(db.String(30))
    link_url = db.Column(db.String(255))

    en_content = db.Column(db.Text)
    ko_content = db.Column(db.Text)
    zh_content = db.Column(db.Text)

    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_editable = db.Column(db.Boolean, nullable=False, default=True)
    is_print_visible = db.Column(db.Boolean, nullable=False, default=True)

    updated_at = db.Column(db.DateTime)