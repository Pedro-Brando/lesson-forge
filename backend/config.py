from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://lesson_forge:lesson_forge_pw@db:5432/lesson_forge"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_FAST: str = "gpt-4o-mini"
    OPENAI_MODEL_GENERATION: str = "gpt-4o"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
