"""Auditable takeoff arithmetic from verified snapshots (not raw CAD commands)."""
from collections import defaultdict
from decimal import Decimal
from .contracts import Marking, QuantityRecord, SignFace
from .validation import validate_faces


def sign_summary(faces: list[SignFace]) -> dict[tuple[str, str, Decimal, Decimal, str], int]:
    """Count faces, never clusters/posts; ignore manual post type."""
    issues = validate_faces(faces)
    if issues:
        raise ValueError("; ".join(f"{i.code}: {i.message}" for i in issues))
    counts = defaultdict(int)
    for f in faces:
        if f.status != "verified":
            raise ValueError(f"Unverified sign face: {f.face_id}")
        key = (f.sign_code, f.shape, f.width_mm, f.height_mm, f.work)
        counts[key] += 1
    return dict(counts)


def painted_area(mark: Marking) -> Decimal | None:
    """Area from actual painted intervals; never infer dash phase from nominal length."""
    if mark.status != "verified" or mark.width_m is None:
        return None
    if not mark.painted_intervals_m:
        return None
    _validate_paint(mark)
    return sum((b - a for a, b in mark.painted_intervals_m), Decimal(0)) * mark.width_m


def _validate_paint(mark: Marking) -> None:
    if (not mark.start_m.is_finite() or not mark.end_m.is_finite()
            or mark.start_m >= mark.end_m):
        raise ValueError("Invalid marking bounds")
    if mark.width_m is None or not mark.width_m.is_finite() or mark.width_m <= 0:
        raise ValueError("Width must be finite and positive")
    intervals = sorted(mark.painted_intervals_m)
    previous_end = None
    for a, b in intervals:
        if not a.is_finite() or not b.is_finite() or a < mark.start_m or b > mark.end_m or a >= b:
            raise ValueError("Paint interval outside marking bounds")
        if previous_end is not None and a < previous_end:
            raise ValueError("Overlapping painted intervals")
        previous_end = b


def segment_area(mark: Marking, ranges: list[tuple[Decimal, Decimal]]) -> list[Decimal | None]:
    """Clip actual paint intervals per station range without resetting dash phase."""
    for start, end in ranges:
        if not start.is_finite() or not end.is_finite() or start >= end:
            raise ValueError("Invalid segment")
    ordered = sorted(ranges)
    if any(b > c for (_, b), (c, _) in zip(ordered, ordered[1:])):
        raise ValueError("Overlapping quantity ranges")
    if mark.status != "verified" or mark.width_m is None or not mark.painted_intervals_m:
        return [None] * len(ranges)
    _validate_paint(mark)
    out = []
    for start, end in ranges:
        clipped = sum((max(Decimal(0), min(b, end) - max(a, start)) for a, b in mark.painted_intervals_m), Decimal(0))
        out.append(clipped * mark.width_m)
    return out


def ledger_for_markings(markings: list[Marking], snapshot_id: str) -> list[QuantityRecord]:
    result = []
    seen = set()
    for m in markings:
        if m.object_id in seen:
            raise ValueError("Duplicate object in takeoff")
        seen.add(m.object_id)
        stale = m.source_snapshot_id != snapshot_id
        area = None if stale else painted_area(m)
        result.append(QuantityRecord(m.object_id, m.marking_code, "m2", area,
                                     "actual painted intervals × verified width", snapshot_id,
                                     issue="stale snapshot" if stale else ("insufficient evidence" if area is None else None)))
    return result
