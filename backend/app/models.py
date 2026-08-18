import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Float, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    source_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    point_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_distance_m: Mapped[float] = mapped_column(Float, default=0)
    matched_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    straight_distance_m: Mapped[float] = mapped_column(Float, default=0)
    max_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    points_json: Mapped[list] = mapped_column(JSON, default=list)
    matched_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    reference_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    findings: Mapped[list["Finding"]] = relationship(cascade="all, delete-orphan", back_populates="trip")

class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    start_index: Mapped[int] = mapped_column(Integer)
    end_index: Mapped[int] = mapped_column(Integer)
    measured_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    explanation: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    trip: Mapped[Trip] = relationship(back_populates="findings")
