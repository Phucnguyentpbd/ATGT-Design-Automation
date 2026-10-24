"""Compare read-only DWG scan results to a locked source manifest.

Inventory integrity is not geometry or sign-code approval.
"""
from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath
import re


def review_flags(relative_path: str) -> tuple[str, ...]:
    """Prioritize manual CAD review; never assign a verified sign_code."""
    normalized = relative_path.replace("\\", "/")
    stem = PurePosixPath(normalized).stem
    flags = ["sign_code_unverified", "cad_geometry_unverified"]
    if not re.fullmatch(r"[A-Za-z]+(?:\.[A-Za-z]+)?\.[A-Za-z0-9,.-]+", stem):
        flags.append("filename_missing_canonical_prefix")
    if "-" in stem or "_" in stem:
        flags.append("legacy_variant_suffix")
    if re.fullmatch(r"[EGH]\d+[A-Za-z]?", stem, flags=re.I):
        flags.append("special_family_identifier")
    if normalized == "Bien_Cam/135.dwg":
        flags.append("crosscheck_DP.135")
    if normalized == "Bien_Chi_Dan/420.dwg":
        flags.append("crosscheck_R.420")
    return tuple(flags)


def validate_against_lock(catalog: dict, locked: dict) -> list[str]:
    """Validate file fingerprints, aggregate sizes and group counts.

    Return reasons rather than silently accepting a partial/wrong directory.
    Compatibility: catalogs emitted by scan_dwg_library, or the detailed
    conversation-side asset manifest. Does not mark CAD assets approved.
    """
    expected = locked.get("inventory", {})
    assets = catalog.get("assets", [])
    issues = []
    total_expected = expected.get("total_dwg", expected.get("total_dwgs"))
    if not isinstance(assets, list):
        return ["assets must be a list"]
    actual_count = len(assets)
    if actual_count != total_expected:
        issues.append(f"DWG count {actual_count}, expected {total_expected}")
    if "total_dwg" in catalog and catalog["total_dwg"] != actual_count:
        issues.append("catalog total_dwg differs from asset rows")
    names = []
    hashes = []
    bytes_actual = 0
    for entry in assets:
        name = entry.get("relative_path", entry.get("source_relative_path", ""))
        normalized = name.replace("\\", "/")
        if (not normalized or normalized.startswith("/")
                or ".." in PurePosixPath(normalized).parts):
            issues.append(f"invalid relative path: {name}")
            continue
        names.append(normalized)
        hashes.append(entry.get("sha256"))
        n = entry.get("size_bytes", -1)
        if not isinstance(n, int) or n <= 0:
            issues.append(f"empty/invalid DWG: {name}")
        else:
            bytes_actual += n
        if entry.get("dwg_header") != expected.get("header", "AC1021"):
            issues.append(f"unexpected header: {name}")
        if not isinstance(entry.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            issues.append(f"invalid checksum: {name}")
    if len(set(names)) != len(names):
        issues.append("duplicate relative paths")
    if len(set(hashes)) != len(hashes):
        issues.append("duplicate DWG checksums require investigation")
    if bytes_actual != expected.get("total_bytes"):
        issues.append(f"total bytes {bytes_actual}, expected {expected.get('total_bytes')}")
    by_group = dict(Counter(PurePosixPath(name).parts[0] for name in names))
    if by_group != expected.get("by_group"):
        issues.append(f"group counts do not match source lock: {by_group}")
    return issues


def make_review_queue(catalog: dict) -> list[dict]:
    """One review task per physical DWG, independent of sign-code identity."""
    result = []
    for asset in catalog.get("assets", []):
        relative_path = asset.get("relative_path", asset.get("source_relative_path"))
        if not relative_path:
            raise ValueError("asset missing relative path")
        flags = review_flags(relative_path)
        result.append({
            "asset_id": asset["asset_id"], "source_relative_path": relative_path,
            "sign_code": None, "sign_code_status": "unverified",
            "geometry_verified": False, "cad_insertion_tested": False,
            "review_flags": list(flags),
        })
    return result
