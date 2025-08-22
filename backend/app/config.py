from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl
from typing import List

class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 30
    stun_servers: str = "stun:stun.l.google.com:19302"
    turn_uri: str | None = None
    turn_username: str | None = None
    turn_password: str | None = None
    cors_origins: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings(
    database_url=None,  # filled by env var DATABASE_URL
    jwt_secret_key=None,
)