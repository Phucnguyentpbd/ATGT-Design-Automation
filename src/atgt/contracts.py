"""Versioned, traceable data contracts for ATGT stages 2-4."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

RoadType = Literal["ordinary", "divided_rural", "urban", "expressway"]
PlacementStatus = Literal["proposed", "verified", "blocked"]
SignWork = Literal["install", "retain", "relocate", "replace_face", "replace_content"]

@dataclass(frozen=True)
class SourceLock:
    reference: str
    version: str
    sha256: str

@dataclass(frozen=True)
class RoadSegment:
    segment_id: str
    road_type: RoadType
    start_m: Decimal
    end_m: Decimal
    reference_alignment: str
    direction_evidence: str | None = None

    def __post_init__(self):
        if self.start_m >= self.end_m:
            raise ValueError("Segment start must precede end")

@dataclass(frozen=True)
class ProjectContext:
    project_id: str
    source_locks: tuple[SourceLock, ...]
    segments: tuple[RoadSegment, ...]
    snapshot_id: str | None = None

@dataclass(frozen=True)
class SignFace:
    face_id: str
    cluster_id: str
    sign_code: str
    shape: str
    width_mm: Decimal
    height_mm: Decimal
    work: SignWork
    asset_id: str | None = None
    status: PlacementStatus = "proposed"
    reference: str | None = None

@dataclass(frozen=True)
class SignCluster:
    cluster_id: str
    alignment_id: str
    station_m: Decimal
    side: Literal["left", "median", "right"]
    sight_direction: str | None = None
    manual_post_type: str | None = None  # Never computed; user-supplied only

@dataclass(frozen=True)
class Marking:
    object_id: str
    marking_code: str
    road_id: str
    start_m: Decimal
    end_m: Decimal
    width_m: Decimal | None
    thickness_mm: Decimal | None
    painted_intervals_m: tuple[tuple[Decimal, Decimal], ...] = ()
    status: PlacementStatus = "proposed"
    source_snapshot_id: str | None = None

@dataclass(frozen=True)
class QuantityRecord:
    object_id: str
    group_key: str
    unit: str
    quantity: Decimal | None
    method: str
    snapshot_id: str
    evidence: str | None = None
    issue: str | None = None
