"""Auditable takeoff arithmetic from verified snapshots (not raw CAD commands)."""
from collections import defaultdict
from decimal import Decimal
from .contracts import Marking, QuantityRecord, SignFace


def sign_summary(faces: list[SignFace]) -> dict[tuple[str, str, Decimal, Decimal, str], int]:
    """Count faces, never clusters/posts; ignore manual post type."""
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
    intervals = sorted(mark.painted_intervals_m)
    length = Decimal("0")
    previous_end = None
    for a, b in intervals:
        if a < mark.start_m or b > mark.end_m or a >= b:
            raise ValueError("Paint interval outside marking bounds")
        if previous_end is not None and a < previous_end:
            raise ValueError("Overlapping painted intervals")
        length += b - a
        previous_end = b
    return length * mark.width_m


def segment_area(mark: Marking, ranges: list[tuple[Decimal, Decimal]]) -> list[Decimal | None]:
    """Clip actual paint intervals per station range without resetting dash phase."""
    if mark.status != "verified" or mark.width_m is None or not mark.painted_intervals_m:
        return [None] * len(ranges)
    out = []
    for start, end in ranges:
        if start >= end:
            raise ValueError("Invalid segment")
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
