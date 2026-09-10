"""Configuration management with validation."""
import logging
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config.yaml"

# Schema for validation: key -> (type, required, default)
CONFIG_SCHEMA = {
    "ai": {
        "_type": dict,
        "_required": True,
        "model": (str, True, "gpt-4o-mini"),
        "temperature": (float, False, 0.7),
        "max_cards": (int, False, 20),
        "max_quiz_questions": (int, False, 10),
        "max_tokens": (int, False, 2048),
    },
    "ingest": {
        "_type": dict,
        "_required": False,
        "ignore": (list, False, []),
    },
    "chunker": {
        "_type": dict,
        "_required": True,
        "chunk_tokens": (int, False, 1200),
        "overlap_tokens": (int, False, 120),
    },
    "tutor": {
        "_type": dict,
        "_required": False,
        "k": (int, False, 6),
        "max_history": (int, False, 10),
    },
    "output": {
        "_type": dict,
        "_required": False,
        "dir": (str, False, "output"),
        "data_dir": (str, False, "data"),
    },
    "study": {
        "_type": dict,
        "_required": False,
        "num_practice_questions": (int, False, 4),
        "title": (str, False, "Study Guide"),
    },
    "spaced_repetition": {
        "_type": dict,
        "_required": False,
        "ease": (float, False, 2.5),
        "learning_interval_min": (int, False, 10),
        "grad_interval_h": (int, False, 24),
    },
    "sync": {
        "_type": dict,
        "_required": False,
        "vault_root": (str, False, ""),
        "amadeus_url": (str, False, "http://127.0.0.1:8000/api/v1/second-brain/sync/learning-tools"),
        "amadeus_export_url": (str, False, "http://127.0.0.1:8000/api/v1/second-brain/sync/kilo-plan/export-all"),
    },
}


def _validate_config(raw: dict) -> list[str]:
    """Validate config against schema. Returns list of warning messages."""
    warnings = []

    for section, fields in CONFIG_SCHEMA.items():
        if section not in raw:
            if fields.get("_required"):
                warnings.append(f"Missing required config section: '{section}'")
            continue

        section_data = raw[section]
        if not isinstance(section_data, dict):
            warnings.append(f"Config section '{section}' should be a mapping, got {type(section_data).__name__}")
            continue

        for key, value_tuple in fields.items():
            if key.startswith("_"):
                continue
            expected_type, required, default = value_tuple
            if key not in section_data:
                if required:
                    warnings.append(f"Missing required config key: '{section}.{key}'")
                continue

            value = section_data[key]
            if value is not None and not isinstance(value, expected_type):
                warnings.append(
                    f"Config '{section}.{key}' should be {expected_type.__name__}, "
                    f"got {type(value).__name__} (value: {value})"
                )

    # Check for unknown sections
    for section in raw:
        if section not in CONFIG_SCHEMA:
            warnings.append(f"Unknown config section: '{section}'")

    return warnings


class Config:
    def __init__(self, path: Path = DEFAULT_CONFIG):
        load_dotenv(PROJECT_ROOT / ".env")

        if not path.exists():
            logger.error(f"Config file not found: {path}")
            sys.exit(1)

        try:
            with open(path, "r", encoding="utf-8") as f:
                self.raw = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in config file {path}: {e}")
            sys.exit(1)

        # Validate
        warnings = _validate_config(self.raw)
        for w in warnings:
            logger.warning(f"Config: {w}")

        self.root = PROJECT_ROOT
        self.sources_dir = PROJECT_ROOT / "sources"
        self.output_dir = PROJECT_ROOT / (self.raw.get("output", {}).get("dir") or "output")
        self.data_dir = PROJECT_ROOT / (self.raw.get("output", {}).get("data_dir") or "data")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def ai(self) -> dict:
        return self.raw.get("ai", {})

    def ingest(self) -> dict:
        return self.raw.get("ingest", {})

    def chunker(self) -> dict:
        return self.raw.get("chunker", {})

    def tutor(self) -> dict:
        return self.raw.get("tutor", {})

    def study(self) -> dict:
        return self.raw.get("study", {})

    def spaced(self) -> dict:
        return self.raw.get("spaced_repetition", {})

    def sync(self) -> dict:
        return self.raw.get("sync", {})

    def api_key(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")

    def base_url(self) -> str:
        return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def vault_root(self) -> Path:
        """Get vault root from config or environment."""
        sync = self.raw.get("sync", {})
        path = sync.get("vault_root") or os.getenv("VAULT_ROOT", "")
        if path:
            return Path(path)
        # Default fallback
        return Path.home() / "MySecondBrain" / "learning-tools"

    def amadeus_url(self) -> str:
        """Get AMADEUS sync URL from config or environment."""
        sync = self.raw.get("sync", {})
        return sync.get("amadeus_url") or os.getenv(
            "AMADEUS_SYNC_URL",
            "http://127.0.0.1:8000/api/v1/second-brain/sync/learning-tools",
        )

    def amadeus_export_url(self) -> str:
        """Get AMADEUS export URL from config or environment."""
        sync = self.raw.get("sync", {})
        return sync.get("amadeus_export_url") or os.getenv(
            "AMADEUS_EXPORT_URL",
            "http://127.0.0.1:8000/api/v1/second-brain/sync/kilo-plan/export-all",
        )

    def amadeus_api_key(self) -> str:
        return os.getenv("AMADEUS_BRAIN_API_KEY", "")


cfg = Config()