# ════════════════════════════════════════════════════════════════
#  Add this file to backend/, next to agent.py.
#
#  It's self-contained — it creates its own ollama.Client the same
#  way agent.py's run_agent_stream() does, using the same env vars
#  (OLLAMA_HOST / OLLAMA_MODEL / OLLAMA_TEMPERATURE etc.), so it
#  doesn't need to import anything from agent.py. That also avoids
#  a circular import, since agent.py needs to import THIS file to
#  register the route.
# ════════════════════════════════════════════════════════════════

import os
import json
import logging

import ollama
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class QuizFromReviewRequest(BaseModel):
    uid: str
    review_content: str
    num_questions: int = 5


QUIZ_PROMPT_TEMPLATE = """You are creating a multiple-choice quiz to test a developer's understanding of the following code review feedback.

Code review content:
---
{review_content}
---

Generate exactly {num_questions} multiple-choice questions based on the specific issues, risks, and recommendations mentioned in this review — not generic programming trivia. Each question should test whether the developer understood *why* something flagged in the review matters.

Respond ONLY with valid JSON in this exact format, with no other text, no markdown fences, no explanation:
{{
  "questions": [
    {{
      "question": "...",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct": "A"
    }}
  ]
}}
"""


def _clean_json_response(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    return cleaned.strip()


def _call_ollama_for_quiz(prompt: str) -> str:
    """Single non-streaming, no-tools completion — same client agent.py uses.

    Reads env vars here (not at module import time) so this always sees
    whatever agent.py's load_dotenv() has loaded, regardless of import order.
    """
    ollama_host        = os.getenv("OLLAMA_HOST",           "http://localhost:11434")
    ollama_model       = os.getenv("OLLAMA_MODEL",          "minimax-m2.5:cloud")
    ollama_temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))
    ollama_top_k       = int(os.getenv("OLLAMA_TOP_K",         "10"))
    ollama_top_p       = float(os.getenv("OLLAMA_TOP_P",       "0.1"))
    ollama_num_ctx     = int(os.getenv("OLLAMA_NUM_CTX",       "8192"))

    client = ollama.Client(host=ollama_host)
    response = client.chat(
        model=ollama_model,
        messages=[{"role": "user", "content": prompt}],
        options={
            "temperature": ollama_temperature,
            "top_p":       ollama_top_p,
            "top_k":       ollama_top_k,
            "num_ctx":     ollama_num_ctx,
        },
    )
    return response.message.content or ""


@router.post("/quiz/generate-from-review")
async def generate_quiz_from_review(req: QuizFromReviewRequest):
    if not req.review_content or not req.review_content.strip():
        return {"error": "No review content available yet. Get a code review first."}

    prompt = QUIZ_PROMPT_TEMPLATE.format(
        review_content=req.review_content[:6000],  # cap prompt size
        num_questions=req.num_questions,
    )

    try:
        raw = _call_ollama_for_quiz(prompt)
        cleaned = _clean_json_response(raw)
        data = json.loads(cleaned)
        questions = data.get("questions", [])

        if not questions:
            return {"error": "Could not generate questions from this review. Try again."}

        return {"questions": questions[: req.num_questions]}

    except json.JSONDecodeError:
        logger.warning("[quiz] Model returned non-JSON: %s", raw[:300] if 'raw' in dir() else "")
        return {"error": "Quiz generation failed — the AI response wasn't valid JSON. Try again."}
    except Exception as e:
        logger.error("[quiz] generate_quiz_from_review error: %s", e)
        return {"error": f"Quiz generation failed: {str(e)}"}