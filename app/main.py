import base64
import re
import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Response
import httpx
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base, get_db
from app.models import ChildProfile, SubmissionHistory, BookRead
from app.schemas import (
    ProfileResponse,
    AdjustPointsRequest,
    ResetStreakRequest,
    GradeResponse,
    SubmissionItemResponse,
    TeacherChatRequest,
    TeacherChatResponse,
    BookScanResponse,
    BookVerifyRequest,
    BookVerifyResponse,
    BookReadItem,
)
from app.services.grading_service import evaluate_and_grade_submission
from app.services.teacher_chat_service import chat_with_teacher
from app.services.book_service import scan_and_question_book, verify_book_comprehension, get_child_bookshelf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        # Seed initial child profiles if not present
        db = next(get_db())
        try:
            if db.query(ChildProfile).count() == 0:
                krisha = ChildProfile(name="Krisha", grade_level="3rd Grade", points=0, consecutive_streak=0)
                vedant = ChildProfile(name="Vedant", grade_level="Kindergarten", points=0, consecutive_streak=0)
                db.add_all([krisha, vedant])
                db.commit()
                logger.info("Initialized default profiles for Krisha and Vedant.")
        finally:
            db.close()
    except OperationalError as e:
        logger.warning(f"Database not available yet at startup: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Allow CORS for zero-auth local network access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v1/health")
def health_check(db: Session = Depends(get_db)):
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "healthy" if db_ok else "database_degraded",
        "database": db_ok,
        "lm_studio_url": settings.LM_STUDIO_URL,
        "model": settings.LM_STUDIO_MODEL
    }

@app.get("/api/v1/profiles", response_model=List[ProfileResponse])
def get_all_profiles(db: Session = Depends(get_db)):
    return db.query(ChildProfile).all()

@app.get("/api/v1/profiles/{name}/points")
def get_points(name: str, db: Session = Depends(get_db)):
    profile = db.query(ChildProfile).filter(ChildProfile.name.ilike(name)).first()
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found.")
    return {
        "name": profile.name,
        "grade_level": profile.grade_level,
        "points": profile.points,
        "streak": profile.consecutive_streak,
        "last_upload_date": profile.last_upload_date
    }

@app.post("/api/v1/profiles/{name}/adjust-points")
def adjust_points(name: str, payload: AdjustPointsRequest, db: Session = Depends(get_db)):
    profile = db.query(ChildProfile).filter(ChildProfile.name.ilike(name)).first()
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found.")
    
    profile.points += payload.adjustment
    db.commit()
    db.refresh(profile)

    # Log manual adjustment in submission history as well
    log_entry = SubmissionHistory(
        child_name=profile.name,
        page_identifier=f"Manual Adjustment ({payload.reason})",
        status="MANUAL_ADJUSTMENT",
        is_correct=payload.adjustment > 0,
        points_awarded=payload.adjustment,
        evaluation_text=f"Points adjusted by {payload.adjustment} ({payload.reason})"
    )
    db.add(log_entry)
    db.commit()

    return {
        "status": "success",
        "name": profile.name,
        "adjustment": payload.adjustment,
        "newPoints": profile.points
    }

@app.post("/api/v1/profiles/{name}/reset-streak")
def reset_streak(name: str, payload: ResetStreakRequest, db: Session = Depends(get_db)):
    profile = db.query(ChildProfile).filter(ChildProfile.name.ilike(name)).first()
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found.")
    
    profile.consecutive_streak = payload.streak
    db.commit()
    db.refresh(profile)
    return {
        "status": "success",
        "name": profile.name,
        "newStreak": profile.consecutive_streak
    }

@app.get("/api/v1/submissions", response_model=List[SubmissionItemResponse])
def get_recent_submissions(limit: int = 50, child_name: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(SubmissionHistory)
    if child_name:
        query = query.filter(SubmissionHistory.child_name.ilike(child_name))
    items = query.order_by(SubmissionHistory.submitted_at.desc()).limit(limit).all()
    # Clean any internal hash markers from evaluation text
    for item in items:
        if item.evaluation_text and "\n[HASH:" in item.evaluation_text:
            item.evaluation_text = item.evaluation_text.split("\n[HASH:")[0]
    return items

@app.post("/api/v1/admin/reset-all")
def reset_all_data(db: Session = Depends(get_db)):
    """
    Wipes submission history and resets points & streaks to 0 for all child profiles.
    """
    try:
        db.query(SubmissionHistory).delete()
        profiles = db.query(ChildProfile).all()
        for p in profiles:
            p.points = 0
            p.consecutive_streak = 0
            p.last_upload_date = None
        db.commit()
        return {"status": "success", "message": "All points, streaks, and submission history have been reset to 0."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/grade", response_model=GradeResponse)
async def grade_homework(
    name: str = Form(...),
    gradeLevel: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    profile = db.query(ChildProfile).filter(ChildProfile.name.ilike(name)).first()
    if not profile:
        # Create profile on the fly if needed
        profile = ChildProfile(name=name, grade_level=gradeLevel, points=0, consecutive_streak=0)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    # Read uploaded file bytes and base64 encode
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    
    base64_img = base64.b64encode(contents).decode("utf-8")
    mime_type = file.content_type or "image/jpeg"

    try:
        result = await evaluate_and_grade_submission(
            db=db,
            child_profile=profile,
            base64_image=base64_img,
            mime_type=mime_type
        )
        return result
    except Exception as e:
        logger.error(f"Grading error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

PRONUNCIATION_MAP = {
    r"\bVedant\b": "Vay-daanth",
    r"\bKrisha\b": "Krish-uh",
}

def apply_pronunciation_fixes(text: str) -> str:
    for pattern, replacement in PRONUNCIATION_MAP.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

@app.get("/api/v1/tts")
async def generate_speech(text: str, voice: Optional[str] = None):
    """
    Proxies to local Kokoro neural TTS container to stream natural human speech.
    Applies phonetic pronunciation substitutions for names.
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    
    spoken_text = apply_pronunciation_fixes(text.strip())
    
    payload = {
        "model": "kokoro",
        "input": spoken_text,
        "voice": voice or settings.KOKORO_VOICE,
        "response_format": "mp3"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(settings.KOKORO_TTS_URL, json=payload)
            if res.status_code == 200:
                return Response(
                    content=res.content, 
                    media_type="audio/mpeg",
                    headers={"Cache-Control": "public, max-age=86400"}
                )
            else:
                logger.error(f"Kokoro returned status {res.status_code}: {res.text}")
                raise HTTPException(status_code=502, detail="TTS generation failed")
    except Exception as e:
        logger.error(f"TTS connection error: {e}")
        raise HTTPException(status_code=503, detail="TTS service unavailable")

@app.post("/api/v1/teacher/chat", response_model=TeacherChatResponse)
async def teacher_voice_chat(payload: TeacherChatRequest):
    """
    Funny teacher conversational turn: explains concepts, mistakes, or tells whimsical stories!
    """
    history_turns = None
    if payload.history:
        history_turns = [{"role": h.role, "content": h.content} for h in payload.history]
    
    reply = await chat_with_teacher(
        child_name=payload.child_name,
        grade_level=payload.grade_level,
        user_message=payload.message,
        page_id=payload.page_identifier,
        evaluation_text=payload.evaluation_text,
        conversation_history=history_turns
    )
    
    import urllib.parse
    audio_url = f"/api/v1/tts?text={urllib.parse.quote(reply)}"
    return {"reply": reply, "audio_url": audio_url}

@app.post("/api/v1/books/scan", response_model=BookScanResponse)
async def scan_book_endpoint(
    name: str = Form(...),
    gradeLevel: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Scans a book cover or ISBN/barcode and generates a targeted comprehension question.
    """
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    
    base64_img = base64.b64encode(contents).decode("utf-8")
    mime_type = file.content_type or "image/jpeg"

    try:
        result = await scan_and_question_book(
            db=db,
            child_name=name,
            grade_level=gradeLevel,
            base64_image=base64_img,
            mime_type=mime_type
        )
        return result
    except Exception as e:
        logger.error(f"Book scan error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/books/verify", response_model=BookVerifyResponse)
async def verify_book_endpoint(
    payload: BookVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Evaluates child's answer to the book comprehension question and awards Reading Star points.
    """
    try:
        result = await verify_book_comprehension(db=db, payload=payload)
        return result
    except Exception as e:
        logger.error(f"Book verify error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/books/shelf/{child_name}", response_model=List[BookReadItem])
async def get_bookshelf_endpoint(
    child_name: str,
    db: Session = Depends(get_db)
):
    """
    Fetches the virtual bookshelf of completed books for the child.
    """
    return get_child_bookshelf(db=db, child_name=child_name)

# Mount static frontend
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
