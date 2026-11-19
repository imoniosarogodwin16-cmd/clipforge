import time
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class Stream(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: str = Field(index=True)
    channel: Optional[str] = None
    duration: float = Field(default=0.0)
    original_url: Optional[str] = None
    audio_path: str
    thumbnail_url: Optional[str] = None
    created_at: float = Field(default_factory=time.time)

    # Relationships
    clips: List["Clip"] = Relationship(back_populates="stream")
    transcript_segments: List["TranscriptSegment"] = Relationship(back_populates="stream")

class Clip(SQLModel, table=True):
    id: str = Field(primary_key=True)
    stream_id: Optional[str] = Field(default=None, foreign_key="stream.id", index=True)
    title: str = Field(index=True)
    part_label: Optional[str] = None
    start_time: float
    end_time: float
    duration: float
    viral_score: int = Field(default=85)
    virality_reason: Optional[str] = None
    layout: str = Field(default="blur_background")
    subtitle_color: str = Field(default="yellow")
    video_path: str
    video_url: str
    file_size_mb: float = Field(default=0.0)
    created_at: float = Field(default_factory=time.time)

    # Relationships
    stream: Optional[Stream] = Relationship(back_populates="clips")
    social_posts: List["SocialMetadata"] = Relationship(back_populates="clip")

class TranscriptSegment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stream_id: str = Field(foreign_key="stream.id", index=True)
    start_time: float
    end_time: float
    text: str = Field(index=True)
    words_json: Optional[str] = None

    # Relationships
    stream: Optional[Stream] = Relationship(back_populates="transcript_segments")

class SocialMetadata(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    clip_id: str = Field(foreign_key="clip.id", index=True)
    platform: str = Field(default="tiktok")
    viral_hook_title: str
    caption: str
    hashtags: str

    # Relationships
    clip: Optional[Clip] = Relationship(back_populates="social_posts")
