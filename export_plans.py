"""Export Kilo plans to Obsidian vault via AMADEUS.

Uses config.yaml for AMADEUS settings.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from lt.config import cfg

logger = logging.getLogger(__name__)


def export_all(plans_dir: str | None = None) -> dict:
    """Export all Kilo plans to Obsidian vault via AMADEUS."""
    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "plans_dir": plans_dir,
            "vault_root": str(cfg.vault_root()),
        }).encode("utf-8")
        req = urllib.request.Request(
            cfg.amadeus_export_url(),
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cfg.amadeus_api_key()}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Export Kilo plans to Obsidian vault via AMADEUS."
    )
    parser.add_argument(
        "--plans-dir",
        help="Path to .kilo/plans directory",
    )
    args = parser.parse_args()

    result = export_all(args.plans_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()