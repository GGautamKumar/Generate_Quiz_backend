from fastapi import APIRouter, UploadFile, File, HTTPException
from models.schemas import QuizConfig, QuizResponse, SubmitRequest, ResultResponse
from services.pdf_service import extract_text_from_pdf
from services.quiz_service import generate_quiz, evaluate_answers
from config import settings

router = APIRouter()

@router.post("/upload-and-generate", response_model=QuizResponse)
async def upload_and_generate(
    file: UploadFile = File(...),
    quiz_type: str = "mcq",
    num_questions: int = 10,
    difficulty: str = "medium"
):
    # Validate file
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    
    content = await file.read()
    if len(content) > settings.max_pdf_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Max {settings.max_pdf_size_mb}MB.")
    
    if num_questions > settings.max_questions:
        raise HTTPException(status_code=400, detail=f"Max {settings.max_questions} questions allowed.")

    # Extract text
    pdf_text = extract_text_from_pdf(content)
    if not pdf_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from PDF.")

    # Generate quiz
    quiz = await generate_quiz(pdf_text, quiz_type, num_questions, difficulty)
    return quiz


@router.post("/submit", response_model=ResultResponse)
async def submit_quiz(payload: SubmitRequest):
    result = await evaluate_answers(payload)
    return result