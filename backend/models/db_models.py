import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def utc_now():
    return datetime.now(timezone.utc)

class UserProfile(Base):
    __tablename__ = 'user_profiles'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True)
    timezone = Column(String, default='UTC')
    notification_enabled = Column(Boolean, default=True)
    baseline_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    entries = relationship("JournalEntry", back_populates="user", cascade="all, delete")
    scores = relationship("MoodScore", back_populates="user", cascade="all, delete")
    nudges = relationship("Nudge", back_populates="user", cascade="all, delete")
    agent_state = relationship("AgentState", back_populates="user", uselist=False, cascade="all, delete")

class JournalEntry(Base):
    __tablename__ = 'journal_entries'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('user_profiles.id', ondelete='CASCADE'), index=True)
    raw_text = Column(Text, nullable=False)
    audio_url = Column(String, nullable=True)
    word_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    user = relationship("UserProfile", back_populates="entries")
    mood_scores = relationship("MoodScore", back_populates="entry")

class MoodScore(Base):
    __tablename__ = 'mood_scores'
    
    # SQLAlchemy requires a primary key, so we use a composite key of time + user_id
    time = Column(DateTime(timezone=True), primary_key=True, default=utc_now)
    user_id = Column(UUID(as_uuid=True), ForeignKey('user_profiles.id', ondelete='CASCADE'), primary_key=True, index=True)
    entry_id = Column(UUID(as_uuid=True), ForeignKey('journal_entries.id'))
    
    text_joy = Column(Float)
    text_sadness = Column(Float)
    text_anger = Column(Float)
    text_fear = Column(Float)
    text_disgust = Column(Float)
    text_surprise = Column(Float)
    text_neutral = Column(Float)
    
    voice_valence = Column(Float)
    voice_arousal = Column(Float)
    voice_energy = Column(Float)
    
    fused_score = Column(Float)
    dominant_emotion = Column(String)
    confidence = Column(Float)
    analysis_version = Column(String)

    user = relationship("UserProfile", back_populates="scores")
    entry = relationship("JournalEntry", back_populates="mood_scores")

class Nudge(Base):
    __tablename__ = 'nudges'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('user_profiles.id', ondelete='CASCADE'))
    nudge_type = Column(String)
    content = Column(Text)
    trigger_reason = Column(Text)
    sent_at = Column(DateTime(timezone=True), default=utc_now)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    rating = Column(Integer, CheckConstraint('rating IN (-1, 0, 1)'))

    user = relationship("UserProfile", back_populates="nudges")

class AgentState(Base):
    __tablename__ = 'agent_states'
    
    user_id = Column(UUID(as_uuid=True), ForeignKey('user_profiles.id'), primary_key=True)
    last_checked_at = Column(DateTime(timezone=True))
    trajectory_slope = Column(Float)
    volatility = Column(Float)
    distress_flag = Column(Boolean, default=False)
    days_since_nudge = Column(Integer, default=0)
    intervention_weights = Column(JSONB)

    user = relationship("UserProfile", back_populates="agent_state")