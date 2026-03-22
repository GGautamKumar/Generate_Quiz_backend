import json
import uuid
import httpx
from fastapi import HTTPException
from models.schemas import (
    QuizResponse, Question,
    SubmitRequest, ResultResponse, QuestionResult
)
from config import settings

QUIZ_TYPE_DESCRIPTIONS = {
    "mcq":        "Multiple Choice Questions (4 options A/B/C/D, one correct)",
    "subjective": "Subjective/short-answer questions requiring written explanation",
    "fill_blank": "Fill in the blank questions with one missing key word/phrase",
    "find_error": "Show a sentence/statement with an error; user must identify the mistake",
}


def _extract_gemini_error_message(payload: dict) -> str:
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    message = error.get("message")
    return message.strip() if isinstance(message, str) and message.strip() else "Gemini request failed."


def _extract_retry_delay_seconds(payload: dict) -> int | None:
    if not isinstance(payload, dict):
        return None

    details = payload.get("error", {}).get("details", [])
    if not isinstance(details, list):
        return None

    for item in details:
        if not isinstance(item, dict):
            continue
        retry_delay = item.get("retryDelay")
        if not isinstance(retry_delay, str):
            continue
        if retry_delay.endswith("s"):
            retry_delay = retry_delay[:-1]
        try:
            return max(1, int(float(retry_delay)))
        except ValueError:
            continue

    return None


def _raise_for_gemini_error(response: httpx.Response) -> None:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if response.status_code == 429:
        retry_after = _extract_retry_delay_seconds(payload or {})
        detail = _extract_gemini_error_message(payload or {})
        headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini quota exceeded or rate limited. "
                f"{detail} Check your Gemini API billing/quota configuration and retry later."
            ),
            headers=headers,
        )

    if response.status_code in (401, 403):
        detail = _extract_gemini_error_message(payload or {})
        raise HTTPException(
            status_code=502,
            detail=(
                "Gemini request was rejected. "
                f"{detail} Verify `GEMINI_API_KEY` and model access."
            ),
        )

    detail = _extract_gemini_error_message(payload or {})
    raise HTTPException(
        status_code=502,
        detail=f"Gemini API error ({response.status_code}): {detail}",
    )

def build_prompt(text: str, quiz_type: str, num_questions: int, difficulty: str) -> str:
    desc = QUIZ_TYPE_DESCRIPTIONS.get(quiz_type, "Mixed questions")
    return f"""You are an expert quiz generator. Based on the following document, generate exactly {num_questions} {desc} at {difficulty} difficulty.

DOCUMENT:
\"\"\"
{text[:12000]}
\"\"\"

Return ONLY a valid JSON array of question objects. No preamble. No markdown. No explanation.

For MCQ and find_error, each object must follow:
{{
  "id": <int>,
  "type": "{quiz_type}",
  "question": "<question text>",
  "options": [{{"label": "A", "text": "..."}}, {{"label": "B", "text": "..."}}, {{"label": "C", "text": "..."}}, {{"label": "D", "text": "..."}}],
  "correct_answer": "<A|B|C|D>",
  "explanation": "<why the answer is correct>"
}}

For subjective and fill_blank, each object must follow:
{{
  "id": <int>,
  "type": "{quiz_type}",
  "question": "<question text>",
  "options": null,
  "correct_answer": "<model answer or missing word>",
  "explanation": "<explanation>"
}}

Generate exactly {num_questions} questions."""


async def _generate_gemini_json(prompt: str, max_output_tokens: int) -> dict | list:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            url,
            params={"key": settings.gemini_api_key},
            json=payload,
        )

    if response.status_code >= 400:
        _raise_for_gemini_error(response)

    body = response.json()
    try:
        raw = body["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Gemini returned an unexpected response structure.",
        ) from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Gemini did not return valid JSON.",
        ) from exc


async def generate_quiz(text: str, quiz_type: str, num_questions: int, difficulty: str) -> QuizResponse:
    prompt = build_prompt(text, quiz_type, num_questions, difficulty)
    data = await _generate_gemini_json(prompt, max_output_tokens=4096)
    questions = [Question(**q) for q in data]

    return QuizResponse(quiz_id=str(uuid.uuid4()), questions=questions)


async def evaluate_answers(payload: SubmitRequest) -> ResultResponse:
    answer_map = {a.question_id: a.answer for a in payload.user_answers}
    results = []
    correct_count = 0

    for q in payload.questions:
        user_ans = answer_map.get(q.id, "").strip()
        
        # For MCQ / find_error: exact match on letter
        if q.type in ("mcq", "find_error"):
            is_correct = user_ans.upper() == q.correct_answer.upper()
            feedback = None
        else:
            # For subjective / fill_blank: use AI to evaluate
            is_correct, feedback = await ai_evaluate_open_answer(
                q.question, q.correct_answer, user_ans, q.type
            )

        if is_correct:
            correct_count += 1

        results.append(QuestionResult(
            question_id=q.id,
            question=q.question,
            user_answer=user_ans,
            correct_answer=q.correct_answer,
            is_correct=is_correct,
            explanation=q.explanation,
            feedback=feedback,
        ))

    total = len(payload.questions)
    score_pct = round((correct_count / total) * 100, 1) if total > 0 else 0
    grade = _grade(score_pct)

    return ResultResponse(
        total=total,
        correct=correct_count,
        score_percent=score_pct,
        grade=grade,
        results=results,
    )


async def ai_evaluate_open_answer(question: str, correct: str, user: str, q_type: str):
    if not user:
        return False, "No answer provided."

    prompt = f"""Evaluate this student answer.
Question: {question}
Model Answer: {correct}
Student Answer: {user}
Question Type: {q_type}

Respond ONLY with valid JSON: {{"is_correct": true/false, "feedback": "<one sentence feedback>"}}"""

    data = await _generate_gemini_json(prompt, max_output_tokens=200)
    return data["is_correct"], data["feedback"]


def _grade(score: float) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"
