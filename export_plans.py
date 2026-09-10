"""Export Kilo plans from learning-tools to the Obsidian vault via AMADEUS."""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

from lt.config import cfg


def export_all(plans_dir: str | None = None) -> dict:
    payload = json.dumps({"plans_dir": plans_dir}).encode("utf-8")
    req = urllib.request.Request(
        cfg.amadeus_export_url(),
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.amadeus_api_key()}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return {"status": "error", "error": f"AMADEUS unreachable: {e}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Kilo plans to Obsidian via AMADEUS.")
    parser.add_argument("--plans-dir", help="Path to .kilo/plans directory")
    args = parser.parse_args()
    result = export_all(args.plans_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
