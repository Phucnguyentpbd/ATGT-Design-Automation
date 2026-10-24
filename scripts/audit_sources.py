#!/usr/bin/env python3
"""Read-only source manifest generator for ATGT Phase 1.

Does not parse DWG geometry, modify source files, or upload binaries.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, is_zipfile

EXPECTED_PDF = "84825a72c4605b65485f3d31a606525a9bc96c970a5200defc0781496ddbbd46"
EXPECTED_XLSX = "97f12717b4479187e93e8889da0ddaf8098dc471609f7f52d94abf849db0b43d"
MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path: Path, kind: str, expected: str | None = None) -> dict:
    result = {"kind": kind, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
    if expected is not None:
        result["matches_locked_sha256"] = result["sha256"] == expected
    return result


def workbook_checks(path: Path) -> dict:
    if not is_zipfile(path):
        raise ValueError("XLSX is not a ZIP package")
    with ZipFile(path) as archive:
        names = archive.namelist()
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = root.find(MAIN_NS + "sheets")
        defined = root.find(MAIN_NS + "definedNames")
        names_of_sheets = [element.get("name") for element in sheets] if sheets is not None else []
        linked = [name for name in names if name.startswith("xl/externalLinks/externalLink") and name.endswith(".xml")]
        cached_ref_errors = 0
        for member in names:
            if not (member.startswith("xl/worksheets/sheet") and member.endswith(".xml")):
                continue
            worksheet = ET.fromstring(archive.read(member))
            for cell in worksheet.iter(MAIN_NS + "c"):
                if cell.get("t") == "e":
                    value = cell.find(MAIN_NS + "v")
                    if value is not None and value.text == "#REF!":
                        cached_ref_errors += 1
        return {
            "sheet_names": names_of_sheets,
            "external_link_parts": len(linked),
            "defined_names": len(defined) if defined is not None else 0,
            "cached_ref_errors": cached_ref_errors,
        }


def audit(qcvn: Path | None, template: Path | None, drawings: list[Path]) -> dict:
    sources = {}
    if qcvn is not None:
        meta = file_identity(qcvn, "qcvn_pdf", EXPECTED_PDF)
        with qcvn.open("rb") as stream:
            meta["header_is_pdf"] = stream.read(5) == b"%PDF-"
        sources["qcvn"] = meta
    if template is not None:
        meta = file_identity(template, "template_xlsx", EXPECTED_XLSX)
        meta.update(workbook_checks(template))
        sources["template_candidate"] = meta
    for index, path in enumerate(drawings, start=1):
        meta = file_identity(path, "dwg_sample")
        with path.open("rb") as stream:
            meta["dwg_header"] = stream.read(6).decode("ascii", errors="replace")
        meta["geometry_verified"] = False
        sources[f"drawing_{index}"] = meta
    return {"schema_version": "1.0", "sources": sources, "no_cad_geometry_verified": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qcvn", type=Path)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--drawing", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.qcvn, args.template, args.drawing)
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
