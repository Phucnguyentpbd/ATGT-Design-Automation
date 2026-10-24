"""Read-only CAD asset inventory. A DWG header is NOT geometric approval."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .validation import validate_sign_code

SIGN_NAME = re.compile(r"^([A-Za-z]+(?:\.[A-Za-z]+)?\.[A-Za-z0-9,.-]+)(?:[_ -].*)?$", re.I)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class CADAsset:
    asset_id: str
    relative_path: str
    size_bytes: int
    sha256: str
    dwg_header: str
    sign_code_candidate: str | None
    status: str = "unverified"
    geometry_verified: bool = False
    units_verified: bool = False


def candidate_code(stem: str) -> str | None:
    """Only a prefixed filename can suggest a candidate; none is approved."""
    match = SIGN_NAME.fullmatch(stem)
    if not match:
        return None
    code = match.group(1)
    return code if validate_sign_code(code) else None


def scan_dwg_library(root: Path) -> dict:
    """Inventory real DWG bytes without reading geometry or modifying files.

    Symlinks are ignored to avoid escaping the selected library directory.
    The local absolute path is deliberately excluded from shareable output.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"DWG library not mounted: {root}")
    assets: list[CADAsset] = []
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix().lower()):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".dwg":
            continue
        rel = path.relative_to(root).as_posix()
        checksum = sha256_file(path)
        with path.open("rb") as handle:
            header = handle.read(6).decode("ascii", errors="replace")
        assets.append(CADAsset(
            asset_id=f"dwg:{rel}:{checksum[:16]}", relative_path=rel,
            size_bytes=path.stat().st_size, sha256=checksum,
            dwg_header=header, sign_code_candidate=candidate_code(path.stem)))
    grouped: dict[str, int] = {}
    for item in assets:
        group = item.relative_path.split("/")[0] if "/" in item.relative_path else "(root)"
        grouped[group] = grouped.get(group, 0) + 1
    return {
        "schema_version": "1.0", "total_dwg": len(assets),
        "total_bytes": sum(a.size_bytes for a in assets),
        "by_group": dict(sorted(grouped.items())),
        "assets": [asdict(a) for a in assets],
        "note": "Unverified inventory; sign code candidates are never insertion authority.",
    }


def write_catalog(catalog: dict, destination: Path) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
