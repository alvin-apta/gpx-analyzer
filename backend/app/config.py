from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./gpx.db"
    redis_url: str = "redis://localhost:6379/0"
    valhalla_url: str = "https://valhalla1.openstreetmap.de"
    ollama_url: str = "http://host.docker.internal:11434/v1"
    ollama_model: str = "qwen3:14b"
    upload_dir: Path = Path("./data/uploads")
    max_upload_bytes: int = 50 * 1024 * 1024
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
