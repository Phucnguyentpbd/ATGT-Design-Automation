"""Versioned, source-bound ATGT block assets for guarded Civil import."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any


MAX_CATALOG_BYTES = 4 * 1024 * 1024
ASSET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.-]{2,159}$")
BLOCK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
SIGN_CODE_RE = re.compile(r"^(?:P|W|R|I|DP|S|IE|RE)\.[0-9]+[A-Za-z]?$", re.I)
MARKING_CODE_RE = re.compile(r"^[1-9]\.[0-9]{1,2}(?:[A-Za-z])?$")
STATUSES = {"review_required", "approved_for_insert", "retired"}
KINDS = {"sign", "marking_block"}
IMPORT_MODES = {"whole_dwg_as_block", "named_block"}


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _finite_number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Asset {field} must be numeric")
    result = float(value)
    if result != result or abs(result) == float("inf"):
        raise ValueError(f"Asset {field} must be finite")
    return result


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    kind: str
    code: str
    source: str
    source_relative_path: str
    source_sha256: str
    import_mode: str
    source_block_name: str | None
    target_block_name: str
    source_units: str
    placement_scale: float
    rotation_offset_rad: float
    extents_size: tuple[float, float, float]
    status: str
    geometry_verified: bool
    units_verified: bool
    review_evidence: str

    def public(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "kind": self.kind,
            "code": self.code,
            "source": self.source,
            "source_relative_path": self.source_relative_path,
            "source_sha256": self.source_sha256,
            "import_mode": self.import_mode,
            "source_block_name": self.source_block_name,
            "target_block_name": self.target_block_name,
            "source_units": self.source_units,
            "placement_scale": self.placement_scale,
            "rotation_offset_rad": self.rotation_offset_rad,
            "extents_size": list(self.extents_size),
            "status": self.status,
            "geometry_verified": self.geometry_verified,
            "units_verified": self.units_verified,
            "review_evidence": self.review_evidence,
        }


class AssetCatalog:
    """Immutable catalog snapshot; selected source bytes are checked on every import."""

    def __init__(self, path: Path, sign_library: Path, marking_template: Path):
        self.path = path.resolve(strict=True)
        self.sign_library = sign_library.resolve(strict=True)
        self.marking_template = marking_template.resolve(strict=True)
        if not self.sign_library.is_dir():
            raise ValueError("Configured sign library is not a directory")
        if not self.marking_template.is_file():
            raise ValueError("Configured marking template is not a file")
        size = self.path.stat().st_size
        if not 1 <= size <= MAX_CATALOG_BYTES:
            raise ValueError(f"Asset catalog must be 1..{MAX_CATALOG_BYTES} bytes")
        self.sha256 = file_sha256(self.path)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Asset catalog is not valid UTF-8 JSON") from exc
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("Asset catalog schema_version must be 1")
        catalog_id = data.get("catalog_id")
        if not isinstance(catalog_id, str) or not re.fullmatch(r"ATGT-ASSETS-[A-Z0-9_-]{3,80}", catalog_id):
            raise ValueError("Asset catalog_id must be a stable ATGT-ASSETS-* identifier")
        raw_assets = data.get("assets")
        if not isinstance(raw_assets, list) or not 1 <= len(raw_assets) <= 5000:
            raise ValueError("Asset catalog must contain 1..5000 assets")
        records: dict[str, AssetRecord] = {}
        target_names: dict[str, str] = {}
        for raw in raw_assets:
            record = self._parse_record(raw)
            if record.asset_id in records:
                raise ValueError(f"Duplicate asset_id: {record.asset_id}")
            folded = record.target_block_name.casefold()
            if folded in target_names and target_names[folded] != record.asset_id:
                raise ValueError(f"Duplicate target block name: {record.target_block_name}")
            records[record.asset_id] = record
            target_names[folded] = record.asset_id
        self.catalog_id = catalog_id
        self.records = records

    def _parse_record(self, raw: Any) -> AssetRecord:
        if not isinstance(raw, dict):
            raise ValueError("Each catalog asset must be an object")
        required = {
            "asset_id", "kind", "code", "source", "source_relative_path",
            "source_sha256", "import_mode", "source_block_name", "target_block_name",
            "source_units", "placement_scale", "rotation_offset_rad", "extents_size",
            "status", "geometry_verified", "units_verified", "review_evidence",
        }
        if set(raw) != required:
            raise ValueError("Catalog asset fields do not match schema")
        asset_id = raw["asset_id"]
        kind = raw["kind"]
        code = raw["code"]
        status = raw["status"]
        mode = raw["import_mode"]
        if not isinstance(asset_id, str) or not ASSET_ID_RE.fullmatch(asset_id):
            raise ValueError("Invalid asset_id")
        if kind not in KINDS or status not in STATUSES or mode not in IMPORT_MODES:
            raise ValueError(f"Invalid kind, status or import mode for {asset_id}")
        if not isinstance(code, str) or not (SIGN_CODE_RE.fullmatch(code) if kind == "sign" else MARKING_CODE_RE.fullmatch(code)):
            raise ValueError(f"Invalid code for {asset_id}")
        source = raw["source"]
        if source not in {"sign_library", "marking_template"}:
            raise ValueError(f"Invalid source for {asset_id}")
        relative = raw["source_relative_path"]
        if not isinstance(relative, str) or not relative or "\\" in relative:
            raise ValueError(f"Invalid relative source path for {asset_id}")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or pure.suffix.lower() != ".dwg":
            raise ValueError(f"Asset path escapes or is not DWG: {asset_id}")
        source_hash = raw["source_sha256"]
        if not isinstance(source_hash, str) or not SHA_RE.fullmatch(source_hash):
            raise ValueError(f"Invalid source SHA-256 for {asset_id}")
        source_block = raw["source_block_name"]
        target_block = raw["target_block_name"]
        if source_block is not None and (not isinstance(source_block, str) or not BLOCK_NAME_RE.fullmatch(source_block)):
            raise ValueError(f"Invalid source block name for {asset_id}")
        if not isinstance(target_block, str) or not BLOCK_NAME_RE.fullmatch(target_block):
            raise ValueError(f"Invalid target block name for {asset_id}")
        if mode == "whole_dwg_as_block" and (source != "sign_library" or source_block is not None):
            raise ValueError(f"Whole-DWG asset must come from sign_library: {asset_id}")
        if mode == "named_block" and (source != "marking_template" or source_block != target_block):
            raise ValueError(f"Named-block asset must preserve its reviewed block name: {asset_id}")
        extents = raw["extents_size"]
        if not isinstance(extents, list) or len(extents) != 3:
            raise ValueError(f"Asset extents_size must have three numbers: {asset_id}")
        extents_tuple = tuple(_finite_number(value, "extents_size") for value in extents)
        if any(value < 0 for value in extents_tuple) or max(extents_tuple) <= 0:
            raise ValueError(f"Asset extents are invalid: {asset_id}")
        geometry_verified = raw["geometry_verified"]
        units_verified = raw["units_verified"]
        evidence = raw["review_evidence"]
        if type(geometry_verified) is not bool or type(units_verified) is not bool:
            raise ValueError(f"Asset review flags must be booleans: {asset_id}")
        if not isinstance(evidence, str) or not 1 <= len(evidence.strip()) <= 1000:
            raise ValueError(f"Asset review evidence is required: {asset_id}")
        if status == "approved_for_insert" and not (geometry_verified and units_verified):
            raise ValueError(f"Approved asset lacks geometry/units review: {asset_id}")
        source_units = raw["source_units"]
        if not isinstance(source_units, str) or not re.fullmatch(r"[A-Za-z]+", source_units):
            raise ValueError(f"Invalid source units for {asset_id}")
        scale = _finite_number(raw["placement_scale"], "placement_scale")
        rotation = _finite_number(raw["rotation_offset_rad"], "rotation_offset_rad")
        if not 0.000001 <= scale <= 1000000:
            raise ValueError(f"Asset placement scale is outside safe bounds: {asset_id}")
        return AssetRecord(
            asset_id=asset_id, kind=kind, code=code, source=source,
            source_relative_path=relative, source_sha256=source_hash,
            import_mode=mode, source_block_name=source_block,
            target_block_name=target_block, source_units=source_units,
            placement_scale=scale, rotation_offset_rad=rotation,
            extents_size=extents_tuple, status=status,
            geometry_verified=geometry_verified, units_verified=units_verified,
            review_evidence=evidence.strip())

    def assert_unchanged(self) -> None:
        if file_sha256(self.path) != self.sha256:
            raise ValueError("Configured asset catalog changed; restart after reviewing the new catalog")

    def source_path(self, record: AssetRecord, require_approved: bool = True) -> Path:
        self.assert_unchanged()
        if require_approved and record.status != "approved_for_insert":
            raise ValueError(f"Asset is not approved_for_insert: {record.asset_id}")
        if record.source == "marking_template":
            if PurePosixPath(record.source_relative_path).name.casefold() != self.marking_template.name.casefold():
                raise ValueError(f"Marking asset does not bind the configured template: {record.asset_id}")
            result = self.marking_template
        else:
            result = (self.sign_library / Path(*PurePosixPath(record.source_relative_path).parts)).resolve(strict=True)
            try:
                result.relative_to(self.sign_library)
            except ValueError as exc:
                raise ValueError(f"Asset escaped the configured sign library: {record.asset_id}") from exc
        if not result.is_file() or result.suffix.lower() != ".dwg":
            raise ValueError(f"Asset DWG is missing: {record.asset_id}")
        if file_sha256(result) != record.source_sha256:
            raise ValueError(f"Asset DWG checksum mismatch: {record.asset_id}")
        return result

    def get(self, asset_id: str, require_approved: bool = False) -> AssetRecord:
        self.assert_unchanged()
        if not isinstance(asset_id, str) or asset_id not in self.records:
            raise ValueError(f"Unknown asset_id: {asset_id}")
        record = self.records[asset_id]
        if require_approved:
            self.source_path(record, require_approved=True)
        return record

    def list(self, kind: str | None = None, code: str | None = None,
             status: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        self.assert_unchanged()
        if kind is not None and kind not in KINDS:
            raise ValueError("Unknown asset kind")
        if status is not None and status not in STATUSES:
            raise ValueError("Unknown asset status")
        if not 1 <= limit <= 100 or not 0 <= offset <= 10000:
            raise ValueError("Use limit 1..100 and offset 0..10000")
        folded_code = code.casefold() if isinstance(code, str) and code else None
        items = [record for record in self.records.values()
                 if (kind is None or record.kind == kind)
                 and (status is None or record.status == status)
                 and (folded_code is None or record.code.casefold() == folded_code)]
        items.sort(key=lambda item: (item.kind, item.code.casefold(), item.asset_id))
        page = items[offset:offset + limit]
        next_offset = offset + len(page)
        if next_offset >= len(items):
            next_offset = None
        return {"items": [deepcopy(item.public()) for item in page],
                "total_count": len(items), "next_offset": next_offset,
                "has_more": next_offset is not None}

    def summary(self) -> dict[str, Any]:
        self.assert_unchanged()
        counts = {status: sum(1 for item in self.records.values() if item.status == status)
                  for status in sorted(STATUSES)}
        return {"catalog_id": self.catalog_id, "sha256": self.sha256,
                "assets": len(self.records), "status_counts": counts}
