from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel

class ProfileResponse(BaseModel):
    name: str
    grade_level: str
    points: int
    consecutive_streak: int
    last_upload_date: Optional[date] = None

    class Config:
        from_attributes = True

class AdjustPointsRequest(BaseModel):
    adjustment: int
    reason: Optional[str] = "Manual Parent Adjustment"

class ResetStreakRequest(BaseModel):
    streak: int = 0

class GradeResponse(BaseModel):
    name: str
    page_identifier: Optional[str]
    is_correct: bool
    status: str  # 'CORRECT', 'INCORRECT', 'CORRECTED', 'ALREADY_COMPLETED'
    points_earned: int
    current_total_points: int
    current_streak: int
    handwriting_bonus: bool
    evaluation_text: str
    message: str

class SubmissionItemResponse(BaseModel):
    id: int
    child_name: str
    page_identifier: Optional[str]
    status: str
    is_correct: bool
    points_awarded: int
    handwriting_bonus: bool
    evaluation_text: Optional[str]
    submitted_at: datetime

    class Config:
        from_attributes = True

class ChatMessage(BaseModel):
    role: str
    content: str

class TeacherChatRequest(BaseModel):
    child_name: str
    grade_level: str
    message: str
    page_identifier: Optional[str] = None
    evaluation_text: Optional[str] = None
    history: Optional[List[ChatMessage]] = None

class TeacherChatResponse(BaseModel):
    reply: str
    audio_url: str

class BookScanResponse(BaseModel):
    title: str
    author: Optional[str] = "Unknown"
    isbn: Optional[str] = None
    question: str
    message: str
    audio_url: Optional[str] = None
    already_read: bool = False

class BookVerifyRequest(BaseModel):
    child_name: str
    grade_level: str
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    question: str
    child_answer: str

class BookVerifyResponse(BaseModel):
    passed: bool
    title: str
    points_earned: int
    current_total_points: int
    feedback: str
    message: str
    audio_url: Optional[str] = None

class BookReadItem(BaseModel):
    id: int
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    points_awarded: int
    completed_at: datetime

    class Config:
        from_attributes = True
