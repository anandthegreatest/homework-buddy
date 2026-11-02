import re
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

async def get_active_model_name(client: httpx.AsyncClient) -> str:
    """
    Attempts to auto-detect the loaded model from LM Studio /v1/models endpoint,
    or falls back to the configured LM_STUDIO_MODEL setting.
    """
    try:
        models_url = settings.LM_STUDIO_URL.split("/chat/completions")[0] + "/models"
        res = await client.get(models_url, timeout=5.0)
        if res.status_code == 200:
            data = res.json()
            models_data = data.get("data", [])
            if models_data:
                active_id = models_data[0].get("id")
                logger.info(f"Using active LM Studio model: {active_id}")
                return active_id
    except Exception as e:
        logger.warning(f"Could not auto-query LM Studio /v1/models: {e}")

    return settings.LM_STUDIO_MODEL if settings.LM_STUDIO_MODEL != "auto" else "default"

def extract_clean_content(content: str, reasoning: str) -> str:
    """
    Extracts strictly the student-facing response, completely discarding internal reasoning/scratchpads.
    """
    target_text = content if content else reasoning
    if not target_text:
        return ""

    # Always attempt to extract any Best Brains page code from anywhere in the text
    found_page_code = None
    code_match = re.search(r"\b([A-Z]{2,4}[0-9a-zA-Z]*\.[0-9]+)\b", target_text)
    if code_match:
        found_page_code = code_match.group(1).strip()
        logger.info("Detected Best Brains page code in output: %s", found_page_code)

    # 1. If content is populated and contains our expected keys, use it
    if content and ("STATUS:" in content.upper() or "PAGE_ID:" in content.upper()):
        clean_content = content.strip()
        # If PAGE_ID was missing from content but found in text, prepend it
        if "PAGE_ID:" not in clean_content.upper() and found_page_code:
            clean_content = f"PAGE_ID: {found_page_code}\n{clean_content}"
        return clean_content

    # 2. Check if the model put the final output block inside reasoning
    markers = [
        r"PAGE_ID:\s*",
        r"STATUS:\s*",
        r"\*\*Drafting the response:?\*\*",
        r"Drafting the response:?",
        r"###\s*Teacher's Review:?",
        r"Teacher's Review:?",
        r"###\s*Summary:?"
    ]

    earliest_idx = -1
    for pattern in markers:
        match = re.search(pattern, target_text, re.IGNORECASE)
        if match:
            if earliest_idx == -1 or match.start() < earliest_idx:
                earliest_idx = match.start()

    if earliest_idx != -1:
        clean = target_text[earliest_idx:].strip()
        if "PAGE_ID:" not in clean.upper() and found_page_code:
            clean = f"PAGE_ID: {found_page_code}\n{clean}"
        logger.info("Successfully extracted clean output from reasoning (discarded %d chars of scratchpad)", earliest_idx)
        return clean

    # 3. If no structured anchor was found, synthesize a clean fallback WITH the detected page code
    logger.warning("No structured markers found in model output; synthesizing clean fallback.")
    page_line = f"PAGE_ID: {found_page_code}\n" if found_page_code else ""

    if "STATUS: CORRECT" in target_text.upper() or "ALL CORRECT" in target_text.upper() or "100% CORRECT" in target_text.upper() or "NO MISTAKES" in target_text.upper():
        return f"{page_line}STATUS: CORRECT\nMISTAKES: None\nFEEDBACK: Great job! All problems on this page are answered correctly."
    else:
        return f"{page_line}STATUS: INCORRECT\nMISTAKES:\n- Please check your worksheet: all problems must be completed and correct.\nFEEDBACK: Review your work and try again!"

async def call_lm_studio_vision(prompt: str, base64_image: str, mime_type: str = "image/jpeg") -> str:
    """
    Sends the prompt and base64-encoded image to LM Studio's completions API.
    """
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            model_name = await get_active_model_name(client)

            payload = {
                "model": model_name,
                "temperature": 0.1,
                "max_tokens": 4500,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ]
            }

            response = await client.post(settings.LM_STUDIO_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("LM Studio returned empty choices.")
            
            message = choices[0].get("message", {})
            content = (message.get("content") or "").strip()
            reasoning = (message.get("reasoning_content") or "").strip()
            
            logger.info("Raw response - Content len: %d, Reasoning len: %d", len(content), len(reasoning))

            clean_result = extract_clean_content(content, reasoning)
            return clean_result
    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to LM Studio at {settings.LM_STUDIO_URL}: {e}")
        raise RuntimeError(
            f"Cannot connect to LM Studio at {settings.LM_STUDIO_URL}. "
            f"Please verify LM Studio is running and local server is started on port 1234."
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"LM Studio returned HTTP error: {e.response.status_code} - {e.response.text}")
        raise RuntimeError(f"LM Studio error ({e.response.status_code}): {e.response.text}")
    except Exception as e:
        logger.error(f"Error during LM Studio inference: {e}")
        raise
