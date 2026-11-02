import re
import logging
import urllib.parse
import httpx
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.config import settings
from app.models import ChildProfile, BookRead
from app.schemas import BookScanResponse, BookVerifyRequest, BookVerifyResponse, BookReadItem
from app.services.lm_studio_client import get_active_model_name

logger = logging.getLogger(__name__)

async def call_book_vision(prompt: str, base64_image: str, mime_type: str = "image/jpeg") -> str:
    """
    Calls LM Studio with the book image to identify the book and formulate a comprehension question.
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            model_name = await get_active_model_name(client)
            payload = {
                "model": model_name,
                "temperature": 0.2,
                "max_tokens": 1500,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                            }
                        ]
                    }
                ]
            }

            res = await client.post(settings.LM_STUDIO_URL, json=payload)
            res.raise_for_status()
            data = res.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("LM Studio returned empty choices.")

            msg = choices[0].get("message", {})
            content = (msg.get("content") or "").strip()
            reasoning = (msg.get("reasoning_content") or "").strip()
            return content if content else reasoning
    except Exception as e:
        logger.error(f"Error calling book vision: {e}", exc_info=True)
        raise

def parse_book_vision_output(raw_text: str, child_name: str, grade_level: str) -> Dict[str, Any]:
    text = raw_text.strip()
    if "<think>" in text and "</think>" in text:
        text = text.split("</think>")[-1].strip()

    title = "Mystery Story"
    author = "Unknown"
    isbn = None
    question = ""

    title_match = re.search(r"TITLE:\s*(.+)", text, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).split("\n")[0].strip().strip('"*#')

    author_match = re.search(r"AUTHOR:\s*(.+)", text, re.IGNORECASE)
    if author_match:
        author = author_match.group(1).split("\n")[0].strip().strip('"*#')

    isbn_match = re.search(r"ISBN:\s*(.+)", text, re.IGNORECASE)
    if isbn_match:
        cand = isbn_match.group(1).split("\n")[0].strip().strip('"*#')
        if cand.lower() not in ["none", "null", "unknown", "n/a", ""]:
            isbn = cand

    q_match = re.search(r"QUESTION:\s*([\s\S]+)", text, re.IGNORECASE)
    if q_match:
        question = q_match.group(1).strip().strip('"*')
    else:
        # Fallback to finding question mark line
        q_lines = [l.strip().strip('"*') for l in text.split("\n") if "?" in l and len(l.strip()) > 15]
        if q_lines:
            question = q_lines[-1]
        else:
            if child_name.lower() == "vedant":
                question = f"What was the funniest or most exciting thing that happened in {title}?"
            else:
                question = f"In {title}, what was the main problem the characters faced and how did they solve it?"

    return {
        "title": title,
        "author": author,
        "isbn": isbn,
        "question": question
    }

async def scan_and_question_book(
    db: Session,
    child_name: str,
    grade_level: str,
    base64_image: str,
    mime_type: str = "image/jpeg"
) -> BookScanResponse:
    """
    Identifies the book cover or ISBN barcode and creates a tailored comprehension question.
    """
    prompt = f"""You are Professor Sunny, the funny owl reading tutor at Best Brains, inspecting a book photo submitted by {child_name}.

CHILD DETAILS:
- Name: {child_name}
- Grade Level: {grade_level}
- Reading Level Notes:
  * Vedant: Reading at late 1st-grade level! Reads early chapter books (Elephant & Piggie, Fly Guy, Frog and Toad, Nate the Great).
  * Krisha: 3rd-grade reader. Reads chapter books (Magic Tree House, Bad Guys, Ramona, Roald Dahl).

INSTRUCTIONS:
1. Identify the BOOK TITLE from the cover, spine, or barcode/ISBN.
2. Identify the AUTHOR (if visible).
3. Extract ISBN or barcode number if visible (otherwise write None).
4. Formulate ONE smart, engaging comprehension question to check if {child_name} read and understood this book:
   - For Vedant: Ask about cause-and-effect, a funny character moment, or how a character felt/reacted.
   - For Krisha: Ask about plot development, character problem-solving, or the lesson learned.
   - The question must be warm, direct, and conversational (1-2 sentences).

CRITICAL FORMAT (DO NOT WRITE SCRATCHPADS):
TITLE: <title>
AUTHOR: <author>
ISBN: <isbn or None>
QUESTION: <single conversational question>
"""

    raw_output = await call_book_vision(prompt, base64_image, mime_type)
    parsed = parse_book_vision_output(raw_output, child_name, grade_level)

    title = parsed["title"]
    author = parsed["author"]
    isbn = parsed["isbn"]
    question = parsed["question"]

    # Check if already completed
    existing = db.query(BookRead).filter(
        BookRead.child_name.ilike(child_name),
        BookRead.title.ilike(title),
        BookRead.passed == True
    ).first()

    already_read = existing is not None

    spoken_intro = f"Ooh, {title}! I love this book! Here is your comprehension question, {child_name}: {question}"
    if already_read:
        spoken_intro = f"Hey {child_name}, you already mastered {title} earlier! Let's do another quick check for fun: {question}"

    audio_url = f"/api/v1/tts?text={urllib.parse.quote(spoken_intro)}"

    return BookScanResponse(
        title=title,
        author=author,
        isbn=isbn,
        question=question,
        message=spoken_intro,
        audio_url=audio_url,
        already_read=already_read
    )

async def verify_book_comprehension(
    db: Session,
    payload: BookVerifyRequest
) -> BookVerifyResponse:
    """
    Evaluates child's spoken or typed answer to the book comprehension question.
    """
    profile = db.query(ChildProfile).filter(ChildProfile.name.ilike(payload.child_name)).first()
    if not profile:
        profile = ChildProfile(name=payload.child_name, grade_level=payload.grade_level, points=0, consecutive_streak=0)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    prompt = f"""You are Professor Sunny, the funny owl reading tutor evaluating whether {payload.child_name} ({payload.grade_level}) read the book "{payload.title}".

BOOK: {payload.title} by {payload.author or 'Unknown'}
COMPREHENSION QUESTION ASKED:
"{payload.question}"

STUDENT'S SPOKEN ANSWER:
"{payload.child_answer}"

EVALUATION CRITERIA:
- Vedant is a late 1st-grade reader; Krisha is a 3rd grader.
- Kids speak naturally with informal phrasing, pauses, or simple descriptions. Be warm and generous!
- If the child's answer describes accurate events, characters, or logical details from the book: PASS: YES.
- If the child gave a completely blank, off-topic, or "I don't know" answer: PASS: NO.

CRITICAL FORMAT:
PASS: <YES or NO>
FEEDBACK: <2-3 cheerful spoken sentences from Professor Sunny. If YES, give enthusiastic praise with a silly analogy! If NO, give a helpful playful hint about the book and ask them to try once more.>
"""

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            model_name = await get_active_model_name(client)
            res = await client.post(
                settings.LM_STUDIO_URL,
                json={
                    "model": model_name,
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            res.raise_for_status()
            data = res.json()
            choices = data.get("choices", [])
            raw_text = ""
            if choices:
                msg = choices[0].get("message", {})
                raw_text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
    except Exception as e:
        logger.error(f"Error evaluating book answer: {e}", exc_info=True)
        raw_text = "PASS: YES\nFEEDBACK: You gave a wonderful answer and showed great effort! Keep on reading!"

    if "<think>" in raw_text and "</think>" in raw_text:
        raw_text = raw_text.split("</think>")[-1].strip()

    pass_match = re.search(r"PASS:\s*(YES|NO)", raw_text, re.IGNORECASE)
    passed = True
    if pass_match:
        passed = (pass_match.group(1).upper() == "YES")

    feedback_match = re.search(r"FEEDBACK:\s*([\s\S]+)", raw_text, re.IGNORECASE)
    if feedback_match:
        feedback = feedback_match.group(1).strip().strip('"*')
    else:
        feedback = raw_text.strip()

    points_earned = 0
    if passed:
        # Check if already awarded points for this book
        already_awarded = db.query(BookRead).filter(
            BookRead.child_name.ilike(payload.child_name),
            BookRead.title.ilike(payload.title),
            BookRead.passed == True
        ).first()

        if not already_awarded:
            points_earned = 15  # Big 15 points milestone for reading a whole book!
            profile.points += points_earned

        # Record reading submission
        record = BookRead(
            child_name=payload.child_name,
            title=payload.title,
            author=payload.author,
            isbn=payload.isbn,
            question_asked=payload.question,
            child_answer=payload.child_answer,
            feedback=feedback,
            points_awarded=points_earned,
            passed=True
        )
        db.add(record)
        db.commit()
        db.refresh(profile)
        msg_text = f"🌟 Fantastic job, {payload.child_name}! You earned +{points_earned} Reading Points!"
    else:
        msg_text = f"Almost there! Professor Sunny has a hint for you."

    spoken_feedback = f"{feedback}"
    audio_url = f"/api/v1/tts?text={urllib.parse.quote(spoken_feedback)}"

    return BookVerifyResponse(
        passed=passed,
        title=payload.title,
        points_earned=points_earned,
        current_total_points=profile.points,
        feedback=feedback,
        message=msg_text,
        audio_url=audio_url
    )

def get_child_bookshelf(db: Session, child_name: str, limit: int = 20) -> List[BookReadItem]:
    """
    Returns list of books completed by the child.
    """
    books = db.query(BookRead).filter(
        BookRead.child_name.ilike(child_name),
        BookRead.passed == True
    ).order_by(BookRead.completed_at.desc()).limit(limit).all()
    
    return [
        BookReadItem(
            id=b.id,
            title=b.title,
            author=b.author,
            isbn=b.isbn,
            points_awarded=b.points_awarded,
            completed_at=b.completed_at
        ) for b in books
    ]
