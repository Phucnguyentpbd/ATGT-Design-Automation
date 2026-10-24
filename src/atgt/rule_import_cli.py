"""Import a reviewed JSON transcription as a draft, not as an executable rule."""
import argparse
import json
from pathlib import Path

from .knowledge import RuleStore


def import_draft(source: Path, database: Path) -> None:
    record = json.loads(source.read_text(encoding="utf-8"))
    if record.get("status") != "draft":
        raise ValueError("Only draft rule import is supported")
    store = RuleStore(database)
    try:
        store.add_draft(record["rule_id"], record["version"], record["source_sha256"],
                        record["citation"], tuple(record["road_types"]), record["payload"])
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    import_draft(args.source, args.database)
    print("Draft imported; not eligible for CAD automation until reviewed and approved")


if __name__ == "__main__":
    main()
