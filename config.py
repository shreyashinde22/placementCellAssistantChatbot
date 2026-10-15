import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    max_message_length: int = 2000
    max_history_messages: int = 6
    max_requests_per_minute: int = 20
    knowledge_base_dir: Path = BASE_DIR / "knowledge_base"

    @classmethod
    def from_environment(cls):
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "").strip(),
        )

    @property
    def api_key_configured(self):
        return bool(self.gemini_api_key)

    @property
    def model_configured(self):
        return bool(self.gemini_model)


settings = Settings.from_environment()
