import json

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str 
    allowed_origins: list[str] = Field(default_factory=list)
    allowed_origin_regex: str | None = r"https://generate-quiz-frontend(?:-[a-z0-9]+)?-gautams-projects-6a7f62ca\.vercel\.app"
    max_pdf_size_mb: int = 10
    max_questions: int = 50

    model_config = SettingsConfigDict(env_file=".env")

    @classmethod
    def _parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return [origin.rstrip("/") for origin in value]

        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(origin).rstrip("/") for origin in parsed]
        except json.JSONDecodeError:
            pass

        return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        def normalized_env_settings():
            data = env_settings()
            origins = data.get("allowed_origins")
            if origins:
                data["allowed_origins"] = cls._parse_origins(origins)
            return data

        def normalized_dotenv_settings():
            data = dotenv_settings()
            origins = data.get("allowed_origins")
            if origins:
                data["allowed_origins"] = cls._parse_origins(origins)
            return data

        return (
            init_settings,
            normalized_env_settings,
            normalized_dotenv_settings,
            file_secret_settings,
        )

settings = Settings()
