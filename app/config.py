from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI / OpenRouter
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"  # override with OpenRouter URL in .env

    # Gmail OAuth2
    gmail_client_id: str
    gmail_client_secret: str
    gmail_redirect_uri: str = "http://localhost:8000/auth/callback"

    # Token encryption key (generate with: Fernet.generate_key())
    encryption_key: str

    # App
    app_secret_key: str = "change-me-in-production"

    class Config:
        env_file = ".env"


settings = Settings()
