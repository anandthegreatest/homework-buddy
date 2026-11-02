import re
import logging
import httpx
from typing import List, Dict, Optional
from app.config import settings
from app.services.lm_studio_client import get_active_model_name

logger = logging.getLogger(__name__)

def build_teacher_system_prompt(
    child_name: str, 
    grade_level: str,
    page_id: Optional[str] = None,
    evaluation_text: Optional[str] = None
) -> str:
    page_context = ""
    if page_id:
        page_context += f"\nWORKSHEET PAGE: {page_id}"
    if evaluation_text:
        page_context += f"\nWORKSHEET EVALUATION:\n{evaluation_text}"

    return f"""You are Professor Sunny, a hilariously funny, warm, and energetic Best Brains teacher speaking directly to {child_name} ({grade_level}).

CRITICAL INSTRUCTIONS:
- DO NOT OVERTHINK. DO NOT WRITE AN OUTLINE, BULLET POINTS, OR SCRATCHPAD.
- START YOUR RESPONSE DIRECTLY WITH YOUR SPOKEN WORDS TO THE CHILD.
- LENGTH: Exactly 2 to 4 friendly, punchy, conversational sentences (suitable for Kokoro voice output).
- TONE: Super funny, goofy, and warm! Use silly analogies (e.g. dancing pizza slices, confused ladybugs, octopuses wearing socks).
- CONCEPTS & MISTAKES: If asked to explain a problem, mistake, or concept, explain the math or English rule simply and humorously with a helpful hint.
- WHIMSICAL FACTS / STORIES: If asked, tell a hilarious 1-sentence fact or mini-story.
- BOUNDARY: Stay strictly focused on homework and learning. Redirection to study if asked off-topic questions.
{page_context}
"""

def extract_teacher_spoken_reply(raw_text: str) -> str:
    """
    Extracts purely the spoken teacher dialogue, discarding any internal monologue, 
    bullet points, or scratchpad notes from thinking models.
    """
    text = raw_text.strip()
    if "<think>" in text and "</think>" in text:
        text = text.split("</think>")[-1].strip()

    # Check if the output is an internal reasoning dump
    is_reasoning_dump = any(marker in text for marker in [
        "Professor Sunny (", "Topic:", "Task:", "Idea 1:", "Option A:", "*Refining", "1. Funny/Goofy?"
    ])

    if is_reasoning_dump:
        # Look for the final quoted dialogue sentence(s)
        quotes = re.findall(r'"([^"\n]{25,})"', text)
        if quotes:
            return quotes[-1].strip()
        
        # If no quotes found, strip lines that look like scratchpads
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        spoken_lines = []
        for l in lines:
            if re.match(r"^(\*|\d+\.|\-)\s+", l) or any(k in l for k in ["Topic:", "Task:", "Idea", "Option", "Refining"]):
                continue
            spoken_lines.append(l)
        if spoken_lines:
            return " ".join(spoken_lines).strip()

    # Remove outer enclosing quotes if whole text is wrapped in them
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].strip()

    return text

async def chat_with_teacher(
    child_name: str,
    grade_level: str,
    user_message: str,
    page_id: Optional[str] = None,
    evaluation_text: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Sends the conversational turn to LM Studio with the funny teacher persona.
    """
    system_prompt = build_teacher_system_prompt(child_name, grade_level, page_id, evaluation_text)

    messages = [{"role": "system", "content": system_prompt}]
    
    if conversation_history:
        for turn in conversation_history[-6:]:  # Keep last 3 turns
            messages.append({"role": turn["role"], "content": turn["content"]})
            
    messages.append({
        "role": "user", 
        "content": f"{user_message}\n\n(Respond directly in 2-4 spoken sentences as Professor Sunny. No scratchpad or bullets.)"
    })

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            model_name = await get_active_model_name(client)
            payload = {
                "model": model_name,
                "temperature": 0.7,
                "max_tokens": 1500,
                "messages": messages
            }

            response = await client.post(settings.LM_STUDIO_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            
            choices = data.get("choices", [])
            if not choices:
                return f"Haha, my goofy teacher brain had a hiccup! Can you say that one more time, {child_name}?"
            
            message = choices[0].get("message", {})
            content = (message.get("content") or "").strip()
            reasoning = (message.get("reasoning_content") or "").strip()

            raw_reply = content if content else reasoning
            clean_reply = extract_teacher_spoken_reply(raw_reply)

            return clean_reply or f"You're doing awesome, {child_name}! What other question do you have about this page?"
    except Exception as e:
        logger.error(f"Teacher chat error: {e}", exc_info=True)
        return f"Whoops! My teacher walkie-talkie lost signal for a second. Ask me again, {child_name}!"
