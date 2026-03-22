from pydantic import BaseModel
from typing import Any, Optional

# ── Quiz generation ──────────────────────────────────────────────
class QuizConfig(BaseModel):
    quiz_type: str          # mcq | subjective | fill_blank | find_error
    num_questions: int
    difficulty: str         # easy | medium | hard

class Option(BaseModel):
    label: str              # A, B, C, D
    text: str

class Question(BaseModel):
    id: int
    type: str               # mcq | subjective | fill_blank | find_error
    question: str
    options: Optional[list[Option]] = None   # only for MCQ / find_error
    correct_answer: str                       # kept server-side but sent to client after submit
    explanation: str

class QuizResponse(BaseModel):
    quiz_id: str
    questions: list[Question]

# ── Submission ───────────────────────────────────────────────────
class UserAnswer(BaseModel):
    question_id: int
    answer: str

class SubmitRequest(BaseModel):
    quiz_id: str
    questions: list[Question]   # full questions for server-side evaluation
    user_answers: list[UserAnswer]

# ── Results ──────────────────────────────────────────────────────
class QuestionResult(BaseModel):
    question_id: int
    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str
    feedback: Optional[str] = None

class ResultResponse(BaseModel):
    total: int
    correct: int
    score_percent: float
    grade: str
    results: list[QuestionResult]