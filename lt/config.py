import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config.yaml"


class Config:
    def __init__(self, path: Path = DEFAULT_CONFIG):
        load_dotenv(PROJECT_ROOT / ".env")
        with open(path, "r", encoding="utf-8") as f:
            self.raw = yaml.safe_load(f) or {}
        self.root = PROJECT_ROOT
        self.sources_dir = PROJECT_ROOT / "sources"
        self.output_dir = PROJECT_ROOT / (self.raw["output"]["dir"] or "output")
        self.data_dir = PROJECT_ROOT / (self.raw["output"]["data_dir"] or "data")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def ai(self):
        return self.raw.get("ai", {})

    def ingest(self):
        return self.raw.get("ingest", {})

    def chunker(self):
        return self.raw.get("chunker", {})

    def tutor(self):
        return self.raw.get("tutor", {})

    def spaced(self):
        return self.raw.get("spaced_repetition", {})

    def api_key(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")

    def base_url(self) -> str:
        return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")


cfg = Config()
