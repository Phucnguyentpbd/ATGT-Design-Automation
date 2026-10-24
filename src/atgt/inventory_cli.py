"""Local read-only inventory: python -m atgt.inventory_cli --sign-library DIR --lin FILE --output manifest.json"""
import argparse
import json
from pathlib import Path
from .assets import scan_dwg_library
from .linetypes import pattern_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sign-library", type=Path)
    parser.add_argument("--lin", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.sign_library and not args.lin:
        parser.error("At least one --sign-library or --lin input is required")
    result = {"schema_version": "1.0", "read_only": True}
    if args.sign_library:
        result["sign_assets"] = scan_dwg_library(args.sign_library)
    if args.lin:
        result["linetypes"] = pattern_manifest(args.lin)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote metadata-only inventory to {args.output}")


if __name__ == "__main__":
    main()
