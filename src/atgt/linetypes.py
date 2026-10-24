"""Parse AutoCAD .LIN stroke patterns as *unapproved* source assets."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .assets import sha256_file

LIN_HEADER = re.compile(r"^\*([^,]+),(.*)$")


@dataclass(frozen=True)
class LineType:
    name: str
    description: str
    elements_m: tuple[Decimal, ...]
    source_sha256: str
    status: str = "unverified"

    @property
    def nominal_cycle_m(self) -> Decimal:
        return sum((abs(v) for v in self.elements_m), Decimal(0))

    @property
    def nominal_paint_m(self) -> Decimal:
        return sum((v for v in self.elements_m if v > 0), Decimal(0))


def parse_lin(path: Path) -> list[LineType]:
    """Read basic A,positive,-negative patterns; reject complex shapes.

    Widths inside descriptions are not verified design parameters.
    """
    raw = Path(path).read_bytes()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("cp1252")
    checksum = sha256_file(Path(path))
    result: list[LineType] = []
    pending: tuple[str, str] | None = None
    names: set[str] = set()
    for rawline in content.splitlines():
        line = rawline.strip()
        if not line or line.startswith(";"):
            continue
        match = LIN_HEADER.match(line)
        if match:
            if pending:
                raise ValueError(f"Missing pattern for {pending[0]}")
            pending = (match.group(1).strip(), match.group(2).strip())
            continue
        if pending is None:
            raise ValueError(f"Orphan .lin pattern: {line}")
        fields = [item.strip() for item in line.split(",")]
        if fields[0].upper() != "A" or len(fields) < 2:
            raise ValueError(f"Unsupported .lin alignment: {pending[0]}")
        try:
            elements = tuple(Decimal(item) for item in fields[1:])
        except InvalidOperation as exc:
            raise ValueError(f"Complex or invalid .lin pattern: {pending[0]}") from exc
        if not elements or elements[0] <= 0 or any(not v.is_finite() for v in elements):
            raise ValueError(f"Invalid initial line segment: {pending[0]}")
        if sum((abs(v) for v in elements), Decimal(0)) <= 0:
            raise ValueError(f"Zero-length .lin cycle: {pending[0]}")
        name, description = pending
        if name.casefold() in names:
            raise ValueError(f"Duplicate .lin name: {name}")
        names.add(name.casefold())
        result.append(LineType(name, description, elements, checksum))
        pending = None
    if pending:
        raise ValueError(f"Missing pattern for {pending[0]}")
    return result


def pattern_manifest(path: Path) -> dict:
    definitions = parse_lin(path)
    return {
        "schema_version": "1.0", "count": len(definitions),
        "patterns": [{**asdict(item), "elements_m": [str(x) for x in item.elements_m],
                      "nominal_cycle_m": str(item.nominal_cycle_m),
                      "nominal_paint_m": str(item.nominal_paint_m)} for item in definitions],
        "warning": "LIN patterns and widths require specialist comparison to QCVN 41:2024; no approval implied.",
    }
