import re
import logging
import hashlib
import datetime
from typing import Tuple, Optional, List, Set
from sqlalchemy.orm import Session
from app.models import ChildProfile, SubmissionHistory
from app.config import settings
from app.services.lm_studio_client import call_lm_studio_vision

logger = logging.getLogger(__name__)

def build_grading_prompt(name: str, grade_level: str) -> str:
    return f"""You are a teacher grading a Best Brains worksheet for {name} ({grade_level}).
DO NOT OVERTHINK. BE DIRECT AND CONCISE (under 100 words total).

CRITICAL INSTRUCTIONS:
1. SINGLE PAGE OR TWO PAGES:
   - Worksheets can be a SINGLE PAGE (e.g. the first or last page of a booklet, such as GM0aV7.8) OR a two-page spread.
   - BOTH are 100% valid, full worksheets! Do NOT think a single page is cropped.
2. ALL QUESTIONS MUST BE COMPLETED:
   - If ANY problem, blank box, bubble, or line match is blank or skipped, output STATUS: INCORRECT with mistake: "Question [X] was left blank."
3. EXACT COUNTING & ARITHMETIC:
   - Count printed objects, dots, and numbers with precision.
   - For skip-counting (e.g. octopus counting by 5's): verify the sequence (e.g. 30, 35, 40, 45, 50).
   - For dice problems: A 6-dot die has 2 parallel rows of 3 dots (6 + 2 = 8 is CORRECT).
4. EXACTLY 1 SENTENCE PER MISTAKE: Clearly specify what was wrong and how to fix it. If 100% correct, write "None".
5. PAGE CODE: Find the Best Brains page code in the bottom corner or top corner (e.g. 'GM0aV7.8', 'GM0aV7.4', 'EH1H2.4', 'ESrRG3.4').

YOU MUST OUTPUT IN THIS EXACT FORMAT (NO PREAMBLE):
PAGE_ID: [Code from corner, e.g. GM0aV7.8, or UNKNOWN]
STATUS: [CORRECT or INCORRECT]
HANDWRITING: [EXCELLENT or STANDARD]
MISTAKES:
- [1 sentence per mistake with advice, or "None"]
FEEDBACK: [1 short encouraging sentence for the student]
"""

def extract_page_tokens(raw_id: Optional[str]) -> Set[str]:
    """
    Extracts individual page tokens from strings like 'GM0aV7.8' or 'EH1H2.4, EH1H2.5'.
    """
    if not raw_id:
        return set()
    cleaned = raw_id.upper().strip()
    if cleaned in ("UNKNOWN", "NONE", "N/A", ""):
        return set()
    
    parts = re.split(r'[,&/\s]+', cleaned)
    tokens = set()
    for p in parts:
        p = p.strip().rstrip("].")
        if len(p) >= 3 and p not in ("AND", "PAGE", "BOOK", "LEVEL", "UNKNOWN", "NONE"):
            tokens.add(p)
    if not tokens and len(cleaned) >= 3:
        tokens.add(cleaned)
    return tokens

def parse_ai_response(response_text: str) -> Tuple[Optional[str], Optional[bool], bool, str]:
    """
    Parses the structured AI output.
    Returns: (page_id, is_correct, handwriting_bonus, explanation)
    """
    if not response_text or len(response_text.strip()) < 15:
        return None, None, False, "AI response was empty or too short."

    cleaned_upper = response_text.upper()

    # 1. Determine Status explicitly
    is_correct: Optional[bool] = None
    if "STATUS: [CORRECT]" in cleaned_upper or "STATUS: CORRECT" in cleaned_upper:
        is_correct = True
    elif "STATUS: [INCORRECT]" in cleaned_upper or "STATUS: INCORRECT" in cleaned_upper:
        is_correct = False
    elif "MISTAKES: NONE" in cleaned_upper and "INCORRECT" not in cleaned_upper:
        is_correct = True

    # 2. Extract Page ID (first try structured PAGE_ID: ..., then fallback to regex)
    page_id = None
    page_id_match = re.search(r"PAGE_ID:\s*\[?([^\]\r\n]+)\]?", response_text, re.IGNORECASE)
    if page_id_match:
        extracted = page_id_match.group(1).strip().rstrip("].")
        if extracted.upper() not in ("UNKNOWN", "NONE", "N/A", ""):
            page_id = extracted

    # Fallback regex for Best Brains page code (e.g. GM0aV7.8)
    if not page_id:
        code_match = re.search(r"\b([A-Z]{2,4}[0-9a-zA-Z]*\.[0-9]+)\b", response_text)
        if code_match:
            page_id = code_match.group(1).strip()
            logger.info("Recovered page code via regex fallback: %s", page_id)

    # 3. Handwriting bonus
    handwriting_bonus = (
        "HANDWRITING: [EXCELLENT]" in cleaned_upper
        or "HANDWRITING: EXCELLENT" in cleaned_upper
    )

    # 4. Extract Mistakes
    mistakes_match = re.search(r"MISTAKES:\s*(.*?)(?=FEEDBACK:|STATUS:|PAGE_ID:|$)", response_text, re.DOTALL | re.IGNORECASE)
    mistakes_text = mistakes_match.group(1).strip() if mistakes_match else ""

    mistake_lines = []
    for line in mistakes_text.splitlines():
        line_clean = line.strip().lstrip("-*• ").strip()
        if line_clean and line_clean.lower() not in ("none", "none.", "n/a", "no mistakes"):
            mistake_lines.append(line_clean)

    # 5. Extract Feedback
    feedback_match = re.search(r"FEEDBACK:\s*\[?(.*?)\]?$", response_text, re.DOTALL | re.IGNORECASE)
    feedback_text = feedback_match.group(1).strip() if feedback_match else ""
    feedback_text = re.sub(r"[\[\]]", "", feedback_text).strip()

    # If mistakes exist, it cannot be correct
    if mistake_lines:
        is_correct = False

    # 6. Check for Tech Error / Incomplete AI generation
    if is_correct is None and not mistake_lines:
        logger.warning("Model failed to provide valid STATUS or MISTAKES. Flagging as TECH_ERROR.")
        return page_id, None, False, "The AI encountered an error processing this page."

    # 7. Build Concise Output
    if is_correct:
        if feedback_text and len(feedback_text) < 150:
            explanation = feedback_text
        else:
            explanation = f"Outstanding work! All problems on {page_id or 'this page'} were answered accurately."
    else:
        parts = []
        if mistake_lines:
            for m in mistake_lines:
                parts.append(f"• {m}")
        else:
            parts.append("• Some answers were incorrect or left blank. Please check every problem on the page.")

        if feedback_text and len(feedback_text) < 150:
            parts.append(feedback_text)
        else:
            parts.append("Fix the items above and rescan to earn your points!")
        explanation = "\n".join(parts)

    return page_id, is_correct, handwriting_bonus, explanation

async def evaluate_and_grade_submission(
    db: Session,
    child_profile: ChildProfile,
    base64_image: str,
    mime_type: str = "image/jpeg"
) -> dict:
    image_hash = hashlib.sha256(base64_image.encode('utf-8')).hexdigest()

    # Check 1: Exact photo duplicate prevention
    recent_identical = (
        db.query(SubmissionHistory)
        .filter(
            SubmissionHistory.child_name == child_profile.name,
            SubmissionHistory.evaluation_text.like(f"%HASH:{image_hash[:16]}%")
        )
        .first()
    )
    if recent_identical:
        return {
            "name": child_profile.name,
            "page_identifier": recent_identical.page_identifier,
            "is_correct": False,
            "status": "ALREADY_COMPLETED",
            "points_earned": 0,
            "current_total_points": child_profile.points,
            "current_streak": child_profile.consecutive_streak,
            "handwriting_bonus": False,
            "evaluation_text": "This exact photo was already submitted. Please scan a new worksheet page!",
            "message": "Duplicate scan detected! No points awarded."
        }

    # Run AI Vision Grading
    prompt = build_grading_prompt(child_profile.name, child_profile.grade_level)
    logger.info("Evaluating worksheet for %s...", child_profile.name)
    raw_ai_text = await call_lm_studio_vision(prompt, base64_image, mime_type)
    logger.info("AI Clean Response:\n%s", raw_ai_text)
    
    page_id, is_correct, handwriting_bonus, explanation = parse_ai_response(raw_ai_text)

    # -------------------------------------------------------------
    # CASE: TECH ERROR / AI FAILED TO EVALUATE
    # -------------------------------------------------------------
    if is_correct is None:
        logger.warning("Tech error detected. Preserving streak: %d", child_profile.consecutive_streak)
        error_explanation = (
            "🤖 The AI had trouble checking this page.\n"
            "Please show this worksheet to a parent to check your answers!\n"
            "Your streak has been preserved."
        )
        history_entry = SubmissionHistory(
            child_name=child_profile.name,
            page_identifier=page_id or "AI Error",
            status="TECH_ERROR",
            is_correct=False,
            points_awarded=0,
            handwriting_bonus=False,
            evaluation_text=f"{error_explanation}\n[HASH:{image_hash[:16]}]",
            submitted_at=datetime.datetime.utcnow()
        )
        db.add(history_entry)
        db.commit()

        return {
            "name": child_profile.name,
            "page_identifier": page_id or "AI Read Error",
            "is_correct": False,
            "status": "TECH_ERROR",
            "points_earned": 0,
            "current_total_points": child_profile.points,
            "current_streak": child_profile.consecutive_streak,
            "handwriting_bonus": False,
            "evaluation_text": error_explanation,
            "message": "Show this page to a parent! AI had trouble reading, so your streak is safe."
        }

    current_tokens = extract_page_tokens(page_id)

    # Check 2: Reject if Page ID is unknown, BUT DO NOT RESET STREAK!
    if not page_id or not current_tokens:
        logger.warning("Submission rejected: Page code not visible. Preserving streak: %d", child_profile.consecutive_streak)
        return {
            "name": child_profile.name,
            "page_identifier": "Unknown Page",
            "is_correct": False,
            "status": "TECH_ERROR",
            "points_earned": 0,
            "current_total_points": child_profile.points,
            "current_streak": child_profile.consecutive_streak,
            "handwriting_bonus": False,
            "evaluation_text": "• Page code in corner was not visible. Make sure the page number in the bottom corner (e.g. GM0aV7.8) is in the picture!\nYour streak is safe.",
            "message": "Page code not visible! Please make sure the bottom corner is shown."
        }

    # Check 3: Check all prior completions to prevent duplicate credit
    prior_completed_submissions = (
        db.query(SubmissionHistory)
        .filter(
            SubmissionHistory.child_name == child_profile.name,
            SubmissionHistory.is_correct == True
        )
        .all()
    )

    already_completed = False
    for sub in prior_completed_submissions:
        sub_tokens = extract_page_tokens(sub.page_identifier)
        if current_tokens.intersection(sub_tokens):
            already_completed = True
            break

    # Check 4: Check if fixing a prior incorrect submission
    prior_incorrect_submission = (
        db.query(SubmissionHistory)
        .filter(
            SubmissionHistory.child_name == child_profile.name,
            SubmissionHistory.is_correct == False
        )
        .order_by(SubmissionHistory.submitted_at.desc())
        .first()
    )
    is_fixing_correction = False
    if prior_incorrect_submission:
        prior_tokens = extract_page_tokens(prior_incorrect_submission.page_identifier)
        if current_tokens.intersection(prior_tokens):
            is_fixing_correction = True

    points_earned = 0
    status_label = "INCORRECT"
    message = ""

    if is_correct:
        if already_completed:
            status_label = "ALREADY_COMPLETED"
            points_earned = 0
            message = f"You already mastered page {page_id}! Great review, but points were already awarded earlier. ⭐"
        elif is_fixing_correction:
            status_label = "CORRECTED"
            child_profile.consecutive_streak += 1
            points_earned = settings.POINTS_CORRECTION_FIX + (child_profile.consecutive_streak * settings.POINTS_PER_STREAK)
            if handwriting_bonus:
                points_earned += settings.POINTS_HANDWRITING_BONUS
            message = f"🌟 Fantastic job correcting your mistakes on page {page_id}! Streak recovered!"
        else:
            status_label = "CORRECT"
            child_profile.consecutive_streak += 1
            points_earned = settings.POINTS_PER_CORRECT + (child_profile.consecutive_streak * settings.POINTS_PER_STREAK)
            if handwriting_bonus:
                points_earned += settings.POINTS_HANDWRITING_BONUS
            message = f"🎉 Perfect score on page {page_id}! Keep up the brilliant work!"
    else:
        status_label = "INCORRECT"
        points_earned = 0
        child_profile.consecutive_streak = 0
        message = "Almost there! Check the corrections below, make your fixes, and rescan to get points!"

    # Save to profile
    child_profile.points += points_earned
    child_profile.last_upload_date = datetime.date.today()
    child_profile.updated_at = datetime.datetime.utcnow()

    # Record in history
    audit_text = f"{explanation}\n[HASH:{image_hash[:16]}]"
    history_entry = SubmissionHistory(
        child_name=child_profile.name,
        page_identifier=page_id,
        status=status_label,
        is_correct=is_correct,
        points_awarded=points_earned,
        handwriting_bonus=handwriting_bonus,
        evaluation_text=audit_text,
        submitted_at=datetime.datetime.utcnow()
    )
    db.add(history_entry)
    db.commit()
    db.refresh(child_profile)

    return {
        "name": child_profile.name,
        "page_identifier": page_id,
        "is_correct": is_correct,
        "status": status_label,
        "points_earned": points_earned,
        "current_total_points": child_profile.points,
        "current_streak": child_profile.consecutive_streak,
        "handwriting_bonus": handwriting_bonus,
        "evaluation_text": explanation,
        "message": message
    }
