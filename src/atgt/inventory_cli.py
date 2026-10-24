"""Local read-only inventory: python -m atgt.inventory_cli --sign-library DIR --lin FILE --output manifest.json"""
import argparse
import json
from pathlib import Path
from .assets import scan_dwg_library
from .linetypes import pattern_manifest
from .library_review import make_review_queue, validate_against_lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sign-library", type=Path)
    parser.add_argument("--lin", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected", type=Path, help="Locked source summary JSON; fails on mismatch")
    parser.add_argument("--review-output", type=Path, help="Unapproved per-DWG CAD review queue JSON")
    args = parser.parse_args()
    if not args.sign_library and not args.lin:
        parser.error("At least one --sign-library or --lin input is required")
    if (args.expected or args.review_output) and not args.sign_library:
        parser.error("--expected and --review-output require --sign-library")
    result = {"schema_version": "1.0", "read_only": True}
    if args.sign_library:
        catalog = scan_dwg_library(args.sign_library)
        if args.expected:
            locked = json.loads(args.expected.read_text(encoding="utf-8"))
            issues = validate_against_lock(catalog, locked)
            if issues:
                raise SystemExit("Source inventory fails locked manifest:\n" + "\n".join(issues))
            result["source_lock_check"] = "matched"
        result["sign_assets"] = catalog
        if args.review_output:
            queue = make_review_queue(catalog)
            args.review_output.parent.mkdir(parents=True, exist_ok=True)
            args.review_output.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.lin:
        result["linetypes"] = pattern_manifest(args.lin)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote metadata-only inventory to {args.output}")


if __name__ == "__main__":
    main()
