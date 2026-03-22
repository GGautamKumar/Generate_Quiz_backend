from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
load_dotenv()

class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    allowed_origins: list[str] = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    max_pdf_size_mb: int = 10
    max_questions: int = 50

    class Config:
        env_file = ".env"

settings = Settings()
