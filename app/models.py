import datetime
from sqlalchemy import Column, String, Integer, Date, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class ChildProfile(Base):
    __tablename__ = "child_profiles"

    name = Column(String(50), primary_key=True, index=True)
    grade_level = Column(String(50), nullable=False)
    points = Column(Integer, default=0, nullable=False)
    consecutive_streak = Column(Integer, default=0, nullable=False)
    last_upload_date = Column(Date, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    submissions = relationship("SubmissionHistory", back_populates="child", cascade="all, delete-orphan")
    books = relationship("BookRead", back_populates="child", cascade="all, delete-orphan")

class SubmissionHistory(Base):
    __tablename__ = "submission_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    child_name = Column(String(50), ForeignKey("child_profiles.name"), nullable=False, index=True)
    page_identifier = Column(String(100), nullable=True, index=True)  # extracted from top right
    status = Column(String(20), nullable=False)  # 'CORRECT', 'INCORRECT', 'CORRECTED', 'DUPLICATE'
    is_correct = Column(Boolean, default=False, nullable=False)
    points_awarded = Column(Integer, default=0, nullable=False)
    handwriting_bonus = Column(Boolean, default=False, nullable=False)
    evaluation_text = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    child = relationship("ChildProfile", back_populates="submissions")

class BookRead(Base):
    __tablename__ = "books_read"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    child_name = Column(String(50), ForeignKey("child_profiles.name"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    author = Column(String(100), nullable=True)
    isbn = Column(String(50), nullable=True)
    question_asked = Column(Text, nullable=True)
    child_answer = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)
    points_awarded = Column(Integer, default=15, nullable=False)
    passed = Column(Boolean, default=True, nullable=False)
    completed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    child = relationship("ChildProfile", back_populates="books")
