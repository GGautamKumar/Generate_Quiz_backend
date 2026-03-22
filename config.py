from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str = "gemini-3-flash-preview"
    allowed_origins: list[str] = ["http://localhost:5173"]
    max_pdf_size_mb: int = 10
    max_questions: int = 50

    class Config:
        env_file = ".env"

settings = Settings()
