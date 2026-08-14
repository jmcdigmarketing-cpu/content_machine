from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TopicScore(Base):
    """Per-topic performance scores (replaces channel_memory.json rows)."""

    __tablename__ = "topic_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    topic: Mapped[str] = mapped_column(String(512), index=True)
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PerformanceEntry(Base):
    """Domain performance log (replaces performance_memory.json entries)."""

    __tablename__ = "performance_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    domain: Mapped[str] = mapped_column(String(64), index=True)
    alignment_score: Mapped[float] = mapped_column(Float, default=0.0)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentRun(Base):
    """One discovery → content → optional render execution."""

    __tablename__ = "content_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    input_topic: Mapped[str] = mapped_column(String(512), default="")
    selected_topic: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="drafted", index=True)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    signals_json: Mapped[str] = mapped_column(Text, default="{}")
    variants_json: Mapped[str] = mapped_column(Text, default="[]")
    title: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    brief_version: Mapped[str] = mapped_column(String(64), default="")
    prompt_version: Mapped[str] = mapped_column(String(64), default="")
    script_preview: Mapped[str] = mapped_column(Text, default="")
    mp3_path: Mapped[str] = mapped_column(String(1024), default="")
    mp4_path: Mapped[str] = mapped_column(String(1024), default="")
    timings_json: Mapped[str] = mapped_column(Text, default="{}")
    abort_reason: Mapped[str] = mapped_column(String(256), default="")
    # Normalized, queryable features for the analytics/intelligence layer:
    # format, angle, title_structure, hook, controversy, sentiment, post_slot,
    # fact_source, cost breakdown, etc. (the moat substrate — Priority #0).
    features_json: Mapped[str] = mapped_column(Text, default="{}")
    # Pre-publish quality scores (Pillar 1): hook score/verdict, authenticity
    # score/verdict, ungrounded count, trade warnings, thumbnail overall —
    # persisted so the grading/calibration layer can read them back.
    quality_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PublishLog(Base):
    """YouTube publish + analytics outcomes linked to a content run."""

    __tablename__ = "publish_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Nullable: rows imported from YouTube analytics (analytics/seed_tapin.py) have no
    # originating run. That was historically written as the sentinel 0, which is not a
    # real run id and blocked the FK — NULL is what SQL means by "no associated run".
    # SET NULL on delete: a published-video record must outlive its run.
    content_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("content_runs.id", ondelete="SET NULL", name="fk_publish_log_content_run"),
        nullable=True,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), default="", unique=True, index=True)
    channel_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    youtube_video_id: Mapped[str] = mapped_column(String(64), default="")
    privacy_status: Mapped[str] = mapped_column(String(32), default="private")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    detail: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    """DB-backed work queue for render / upload / discovery."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    job_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    content_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("content_runs.id", ondelete="SET NULL", name="fk_jobs_content_run"),
        nullable=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str] = mapped_column(Text, default="")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ThumbnailScore(Base):
    """Pre-publish thumbnail clickability scores (CTR correlation later)."""

    __tablename__ = "thumbnail_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # CASCADE, not SET NULL: a thumbnail score is meaningless without its run.
    content_run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("content_runs.id", ondelete="CASCADE", name="fk_thumbnail_scores_content_run"),
        index=True,
    )
    channel_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    image_path: Mapped[str] = mapped_column(String(1024), default="")
    topic: Mapped[str] = mapped_column(String(512), default="")
    curiosity: Mapped[float] = mapped_column(Float, default=0.0)
    clarity: Mapped[float] = mapped_column(Float, default=0.0)
    contrast: Mapped[float] = mapped_column(Float, default=0.0)
    emotion: Mapped[float] = mapped_column(Float, default=0.0)
    overall: Mapped[float] = mapped_column(Float, default=0.0)
    suggestions_json: Mapped[str] = mapped_column(Text, default="[]")
    source: Mapped[str] = mapped_column(String(16), default="heuristic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Asset(Base):
    """Catalogued media files (backgrounds, thumbnails) linked to runs."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    content_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("content_runs.id", ondelete="SET NULL", name="fk_assets_content_run"),
        nullable=True,
        index=True,
    )
    asset_type: Mapped[str] = mapped_column(String(32), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="")
    source_id: Mapped[str] = mapped_column(String(128), default="")
    path: Mapped[str] = mapped_column(String(1024), default="")
    query: Mapped[str] = mapped_column(String(512), default="")
    attribution: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
