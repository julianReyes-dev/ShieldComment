from datetime import datetime
from .database import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.sql import func

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    offense_count = Column(Integer, default=0)
    is_blocked = Column(Boolean, default=False)
    blocked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    metadata_ = Column(JSON, nullable=True)  # Additional user metadata

class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CommentAnalysis(Base):
    __tablename__ = "comment_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"))
    toxicity_score = Column(Integer)  # Score from 0 to 100
    classification = Column(String)  # "non-toxic", "potentially-toxic", "toxic"
    analysis_result = Column(JSON)  # Full analysis result in JSONB
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
