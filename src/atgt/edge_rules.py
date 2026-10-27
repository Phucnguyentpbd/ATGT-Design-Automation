"""Explainable 3.1a/3.1b proposals. Does not authorize or execute CAD writes.

Offsets are the user's project practice, measured to the paint CENTERLINE.
The QCVN outer-edge clearance is measured to the OUTSIDE of the paint.
Each input is one already classified interval; intersection extents are never
guessed from a point and turning permission is never inferred from geometry.
"""
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json

from .linetypes import LineType

D = Decimal
QCVN_REFERENCE = "QCVN 41:2024/BGTVT, G1.3(a), PDF pages 166-167, figure G.13a"
PROFILE_ID = "USER-EDGE-20261024-v1"
SUPPORTED = {"ordinary", "divided_rural"}


def _has_reference(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True)
class EdgeContext:
    snapshot_id: str
    alignment_id: str
    edge_handle: str
    road_type: str
    edge_role: str  # outer_pavement or median
    scenario: str  # continuous, local_access or median_opening
    start_m: Decimal
    end_m: Decimal
    width_m: Decimal  # Explicit project choice, never inferred from LIN text
    carriageway_width_m: Decimal
    available_paved_width_m: Decimal  # Distance toward carriageway from this edge
    boundary_evidence: str
    direction_evidence: str
    outer_edge_matches_running_edge: bool | None = None
    turning_permitted: bool | None = None
    movement_evidence: str | None = None
    special_necessity_evidence: str | None = None


def propose_edge_marking(context: EdgeContext, patterns: list[LineType]) -> dict:
    c = context
    issues = []
    if c.road_type not in SUPPORTED:
        issues.append("unsupported_road_type")
    if c.edge_role not in {"outer_pavement", "median"}:
        issues.append("unclassified_edge")
    if c.scenario not in {"continuous", "local_access", "median_opening"}:
        issues.append("scenario_requires_other_rule")
    if c.scenario == "median_opening" and (c.edge_role != "median" or c.road_type != "divided_rural"):
        issues.append("median_opening_requires_divided_road_median")
    if c.edge_role == "median" and c.road_type != "divided_rural":
        issues.append("median_requires_divided_road_classification")
    for name in ("snapshot_id", "alignment_id", "edge_handle", "boundary_evidence", "direction_evidence"):
        if not isinstance(getattr(c, name), str) or not getattr(c, name).strip():
            issues.append("missing_" + name)
    numbers = (c.start_m, c.end_m, c.width_m, c.carriageway_width_m, c.available_paved_width_m)
    finite = all(isinstance(x, Decimal) and x.is_finite() for x in numbers)
    if not finite:
        issues.append("invalid_numeric_input")
    else:
        if c.start_m >= c.end_m:
            issues.append("invalid_interval")
        if not D("0.15") <= c.width_m <= D("0.20"):
            issues.append("width_outside_qcvn_3_1")
        if c.carriageway_width_m <= 0 or c.available_paved_width_m <= 0:
            issues.append("invalid_paved_width")
        if c.carriageway_width_m < D(7) and not _has_reference(c.special_necessity_evidence):
            issues.append("under_7m_requires_necessity_evidence")
    if c.edge_role == "outer_pavement" and c.outer_edge_matches_running_edge is not True:
        issues.append("outer_pavement_vs_running_edge_unresolved")
    crossing = c.scenario in {"local_access", "median_opening"}
    if crossing and (c.turning_permitted is not True or not _has_reference(c.movement_evidence)):
        issues.append("turning_permission_not_confirmed")
    code = "3.1b" if crossing else "3.1a"
    offset = D("0.30") if c.edge_role == "outer_pavement" else D("0.50")
    clearance = offset - c.width_m / 2 if finite else None
    if finite:
        if offset + c.width_m / 2 > c.available_paved_width_m:
            issues.append("paint_outside_available_pavement")
        if c.edge_role == "outer_pavement" and not D("0.15") <= clearance <= D("0.30"):
            issues.append("outer_clearance_outside_qcvn")
    linetype = "Continuous"
    if code == "3.1b":
        matches = [p for p in patterns if "3.1B" in p.name.upper()
                   and p.elements_m == (D("0.6"), D("-0.6"))]
        if len(matches) != 1:
            issues.append("missing_or_ambiguous_3_1b_0_6_pattern")
            linetype = None
        else:
            linetype = matches[0].name
    key = [PROFILE_ID, c.snapshot_id, c.alignment_id, c.edge_handle, str(c.start_m), str(c.end_m), code]
    return {
        "proposal_id": "edge:" + hashlib.sha256(json.dumps(key).encode()).hexdigest()[:24],
        "status": "blocked" if issues else "proposed",
        "cad_execution_allowed": False,
        "issues": issues,
        "snapshot_id": c.snapshot_id,
        "alignment_id": c.alignment_id,
        "edge_handle": c.edge_handle,
        "interval_m": [str(c.start_m), str(c.end_m)],
        "marking_code": None if issues else code,
        "candidate_marking_code": code,
        "centerline_offset_m": str(offset),
        "offset_direction": "toward_carriageway",
        "outside_paint_clearance_m": str(clearance) if clearance is not None else None,
        "width_m": str(c.width_m), "color": "white", "linetype": linetype,
        "paint_gap_m": ["0.6", "0.6"] if code == "3.1b" else None,
        "basis": {
            "offset": {"kind": "user_project_practice", "profile": PROFILE_ID},
            "qcvn": {"citation": QCVN_REFERENCE, "scope": "width/pattern/outer-edge clearance and applicability"},
            "movement": c.movement_evidence,
        },
        "pending_checks": ["offset_geometry_and_local_normal", "actual_units_and_linetype_scale",
                           "asset_geometry_review", "independent_design_review", "CAD_readback"],
        "notes": ["Median offset 0.50 m is user practice, not a quoted QCVN outer-edge requirement.",
                  "3.1a does not by itself establish a prohibition on crossing or turning.",
                  "Station interval length is not a measured paint length on offset curves."],
    }


def context_from_dict(data: dict) -> EdgeContext:
    data = dict(data)
    for name in ("start_m", "end_m", "width_m", "carriageway_width_m", "available_paved_width_m"):
        if isinstance(data.get(name), bool):
            raise ValueError(f"{name} must be a decimal in metres")
        data[name] = D(str(data[name]))
    for name in ("outer_edge_matches_running_edge", "turning_permitted"):
        if data.get(name) is not None and type(data[name]) is not bool:
            raise ValueError(f"{name} must be true, false or null")
    return EdgeContext(**data)
