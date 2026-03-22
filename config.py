from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str 
    allowed_origins: list[str] 
    max_pdf_size_mb: int = 10
    max_questions: int = 50

    class Config:
        env_file = ".env"

settings = Settings()
