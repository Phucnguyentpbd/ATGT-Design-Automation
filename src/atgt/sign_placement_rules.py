"""Source-separated sign placement proposals; never authorizes CAD writes.

QCVN-specific positions take precedence.  The TCVN 4054 stopping-sight-distance
table is a user-approved fallback only after a QCVN search has established that
no numeric placement distance applies.  Junction grouping is likewise kept
separate from the cited QCVN W.207d/e rule.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import re


D = Decimal
SUPPORTED = {"ordinary", "divided_rural"}
PROFILE_ID = "USER-SIGN-20261026-v1"
TCVN_4054_PDF_SHA = "b3ddcc3424dec93e9bc2b83ba0d3dc9d42f472bdcf4149e6ff6c8dde0a5359f1"
TCVN_REFERENCE = "TCVN 4054:2005, 5.1.1, Table 10, PDF page 19"
QCVN_GENERAL_REFERENCE = "QCVN 41:2024/BGTVT, Article 30.1-30.5, PDF page 25"
QCVN_W205_REFERENCE = "QCVN 41:2024/BGTVT, Annex C.5, PDF page 100"
QCVN_W207_REFERENCE = "QCVN 41:2024/BGTVT, Annex C.7(a-d), PDF pages 100-101"
QCVN_S501_REFERENCE = "QCVN 41:2024/BGTVT, Annex F.1, PDF page 151"

STOPPING_SIGHT_DISTANCE_M = {
    20: D("20"), 30: D("30"), 40: D("40"), 60: D("75"),
    80: D("100"), 100: D("150"), 120: D("210"),
}

W205_RE = re.compile(r"W\.205[a-e]")
W207_RE = re.compile(r"W\.207(?:[a-i]|k|l)")


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite(value) -> bool:
    return isinstance(value, Decimal) and value.is_finite()


def _upstream_station(target: Decimal, distance: Decimal, direction: str) -> Decimal:
    return target - distance if direction == "increasing" else target + distance


def _round_tens(value: Decimal) -> Decimal:
    return (value / D("10")).quantize(D("1"), rounding=ROUND_HALF_UP) * D("10")


@dataclass(frozen=True)
class SignPositionContext:
    snapshot_id: str
    alignment_id: str
    target_id: str
    sign_code: str
    road_type: str
    travel_direction: str
    design_speed_kmh: int
    alignment_start_m: Decimal
    alignment_end_m: Decimal
    target_station_m: Decimal
    qcvn_search_evidence: str
    qcvn_no_numeric_distance_confirmed: bool
    qcvn_distance_m: Decimal | None = None
    qcvn_distance_reference: str | None = None


@dataclass(frozen=True)
class Junction:
    junction_id: str
    station_m: Decimal
    priority_relationship: str
    candidate_sign_code: str
    branch_side: str
    geometry_evidence: str
    priority_evidence: str


@dataclass(frozen=True)
class JunctionWarningContext:
    snapshot_id: str
    alignment_id: str
    road_type: str
    travel_direction: str
    design_speed_kmh: int
    alignment_start_m: Decimal
    alignment_end_m: Decimal
    qcvn_search_evidence: str
    junctions: tuple[Junction, ...]


def _base_issues(snapshot_id: str, alignment_id: str, road_type: str, travel_direction: str,
                 design_speed_kmh: int, start: Decimal, end: Decimal,
                 qcvn_search_evidence: str) -> list[str]:
    issues = []
    if road_type not in SUPPORTED:
        issues.append("unsupported_road_type")
    if travel_direction not in {"increasing", "decreasing"}:
        issues.append("invalid_travel_direction")
    if design_speed_kmh not in STOPPING_SIGHT_DISTANCE_M:
        issues.append("design_speed_not_in_tcvn4054_table10")
    if not _text(snapshot_id):
        issues.append("missing_snapshot_id")
    if not _text(alignment_id):
        issues.append("missing_alignment_id")
    if not _text(qcvn_search_evidence):
        issues.append("missing_qcvn_search_evidence")
    if not (_finite(start) and _finite(end)) or start >= end:
        issues.append("invalid_alignment_range")
    return issues


def propose_sign_position(context: SignPositionContext, *, tcvn_source_verified: bool) -> dict:
    c = context
    issues = _base_issues(c.snapshot_id, c.alignment_id, c.road_type, c.travel_direction,
                          c.design_speed_kmh, c.alignment_start_m, c.alignment_end_m,
                          c.qcvn_search_evidence)
    if not _text(c.target_id):
        issues.append("missing_target_id")
    if not _text(c.sign_code) or not re.fullmatch(r"(?:P|W|R|I|DP|S|IE|RE)\.[0-9]+[A-Za-z]?", c.sign_code):
        issues.append("invalid_full_sign_code")
    if not _finite(c.target_station_m):
        issues.append("invalid_target_station")
    elif _finite(c.alignment_start_m) and _finite(c.alignment_end_m) and not (
            c.alignment_start_m <= c.target_station_m <= c.alignment_end_m):
        issues.append("target_outside_alignment_range")

    if c.qcvn_distance_m is not None:
        if not _finite(c.qcvn_distance_m) or c.qcvn_distance_m < 0:
            issues.append("invalid_qcvn_distance")
            distance = D("0")
        else:
            distance = c.qcvn_distance_m
        if not _text(c.qcvn_distance_reference):
            issues.append("qcvn_distance_requires_reference")
        basis_kind = "qcvn_explicit_position"
        basis_reference = c.qcvn_distance_reference
    else:
        distance = STOPPING_SIGHT_DISTANCE_M.get(c.design_speed_kmh, D("0"))
        if c.qcvn_no_numeric_distance_confirmed is not True:
            issues.append("qcvn_numeric_distance_status_unresolved")
        if not tcvn_source_verified:
            issues.append("tcvn4054_source_not_configured_or_verified")
        basis_kind = "tcvn4054_stopping_sight_distance_fallback"
        basis_reference = TCVN_REFERENCE

    station = _upstream_station(c.target_station_m, distance, c.travel_direction)
    if _finite(c.alignment_start_m) and _finite(c.alignment_end_m) and not (
            c.alignment_start_m <= station <= c.alignment_end_m):
        issues.append("placement_outside_alignment_range")
    key = [PROFILE_ID, c.snapshot_id, c.alignment_id, c.target_id, c.sign_code,
           str(c.target_station_m), str(distance), c.travel_direction]
    return {
        "proposal_id": "sign:" + hashlib.sha256(json.dumps(key).encode()).hexdigest()[:24],
        "status": "blocked" if issues else "proposed",
        "cad_execution_allowed": False,
        "issues": issues,
        "snapshot_id": c.snapshot_id,
        "alignment_id": c.alignment_id,
        "target_id": c.target_id,
        "sign_code": c.sign_code,
        "target_station_m": str(c.target_station_m),
        "placement_station_m": None if issues else str(station),
        "distance_before_target_m": str(distance),
        "travel_direction": c.travel_direction,
        "basis": {
            "precedence": "QCVN-specific position before TCVN 4054 fallback",
            "kind": basis_kind,
            "reference": basis_reference,
            "qcvn_search_evidence": c.qcvn_search_evidence,
            "qcvn_general": QCVN_GENERAL_REFERENCE,
        },
        "pending_checks": ["actual_forward_visibility", "roadside_clearance_and_obstruction",
                           "native_station_geometry", "asset_geometry_review",
                           "independent_design_review", "CAD_readback"],
    }


def _junction_issue(j: Junction) -> str | None:
    if not _text(j.junction_id) or not _finite(j.station_m):
        return "invalid_junction_identity_or_station"
    if j.priority_relationship == "equal":
        if not W205_RE.fullmatch(j.candidate_sign_code):
            return "equal_priority_requires_w205_variant"
    elif j.priority_relationship == "side_road_non_priority":
        if not W207_RE.fullmatch(j.candidate_sign_code):
            return "non_priority_branch_requires_w207_variant"
    else:
        return "unresolved_priority_relationship"
    if j.branch_side not in {"left", "right", "both"}:
        return "invalid_branch_side"
    if not _text(j.geometry_evidence) or not _text(j.priority_evidence):
        return "missing_junction_evidence"
    return None


def _encounter_order(junctions: tuple[Junction, ...], direction: str) -> list[Junction]:
    return sorted(junctions, key=lambda j: j.station_m, reverse=direction == "decreasing")


def _group_junctions(junctions: list[Junction], sight: Decimal) -> list[list[Junction]]:
    groups: list[list[Junction]] = []
    for junction in junctions:
        if not groups or abs(junction.station_m - groups[-1][-1].station_m) >= sight:
            groups.append([junction])
        else:
            groups[-1].append(junction)
    return groups


def propose_junction_warnings(context: JunctionWarningContext, *, tcvn_source_verified: bool) -> dict:
    c = context
    issues = _base_issues(c.snapshot_id, c.alignment_id, c.road_type, c.travel_direction,
                          c.design_speed_kmh, c.alignment_start_m, c.alignment_end_m,
                          c.qcvn_search_evidence)
    if not tcvn_source_verified:
        issues.append("tcvn4054_source_not_configured_or_verified")
    if not c.junctions:
        issues.append("no_junctions")
    seen = set()
    for junction in c.junctions:
        issue = _junction_issue(junction)
        if issue:
            issues.append(f"{junction.junction_id or 'junction'}:{issue}")
        if junction.junction_id in seen:
            issues.append(f"{junction.junction_id}:duplicate_junction_id")
        seen.add(junction.junction_id)
        if (_finite(junction.station_m) and _finite(c.alignment_start_m) and
                _finite(c.alignment_end_m) and not c.alignment_start_m <= junction.station_m <= c.alignment_end_m):
            issues.append(f"{junction.junction_id}:junction_outside_alignment_range")
    sight = STOPPING_SIGHT_DISTANCE_M.get(c.design_speed_kmh, D("0"))
    ordered = _encounter_order(c.junctions, c.travel_direction)
    groups = _group_junctions(ordered, sight) if not issues else []
    placements = []
    for index, group in enumerate(groups, 1):
        first, last = group[0], group[-1]
        placement = _upstream_station(first.station_m, sight, c.travel_direction)
        group_issues = []
        if not c.alignment_start_m <= placement <= c.alignment_end_m:
            group_issues.append("placement_outside_alignment_range")
        relationships = {j.priority_relationship for j in group}
        if len(group) == 1:
            sign_code = first.candidate_sign_code
            rule_kind = "single_junction_by_actual_priority_and_geometry"
            s501 = None
        elif relationships == {"side_road_non_priority"}:
            if first.branch_side == "right":
                sign_code = "W.207d"
            elif first.branch_side == "left":
                sign_code = "W.207e"
            else:
                sign_code = None
                group_issues.append("aggregate_w207d_or_w207e_requires_nearest_branch_side")
            rule_kind = "qcvn_w207_dense_sequence"
            s501 = _round_tens(abs(last.station_m - placement))
        else:
            # User-approved practice: retain the family/variant of the first junction
            # encountered from the sign, never silently convert W.205 to W.207.
            sign_code = first.candidate_sign_code
            rule_kind = "user_approved_cluster_retains_nearest_junction_family"
            s501 = _round_tens(abs(last.station_m - placement))
        placements.append({
            "group_id": f"junction-group-{index}",
            "status": "blocked" if group_issues else "proposed",
            "issues": group_issues,
            "junction_ids": [j.junction_id for j in group],
            "representative_sign_code": sign_code,
            "placement_station_m": None if group_issues else str(placement),
            "distance_before_first_junction_m": str(sight),
            "first_junction_station_m": str(first.station_m),
            "last_junction_station_m": str(last.station_m),
            "s501_required": len(group) > 1,
            "s501_length_m": str(s501) if s501 is not None else None,
            "s501_rounding": "nearest_10_m_half_up" if s501 is not None else None,
            "rule_kind": rule_kind,
            "nearest_junction_priority_relationship": first.priority_relationship,
            "nearest_junction_geometry_evidence": first.geometry_evidence,
        })
    blocked = bool(issues) or any(p["status"] == "blocked" for p in placements)
    key = [PROFILE_ID, c.snapshot_id, c.alignment_id, c.design_speed_kmh, c.travel_direction,
           [(j.junction_id, str(j.station_m), j.priority_relationship, j.candidate_sign_code)
            for j in ordered]]
    return {
        "proposal_id": "junction-signs:" + hashlib.sha256(json.dumps(key).encode()).hexdigest()[:24],
        "status": "blocked" if blocked else "proposed",
        "cad_execution_allowed": False,
        "issues": issues,
        "snapshot_id": c.snapshot_id,
        "alignment_id": c.alignment_id,
        "design_speed_kmh": c.design_speed_kmh,
        "stopping_sight_distance_m": str(sight),
        "grouping_threshold": "consecutive station gap < S1",
        "placements": placements,
        "basis": {
            "qcvn_w205": QCVN_W205_REFERENCE,
            "qcvn_w207": QCVN_W207_REFERENCE,
            "qcvn_s501": QCVN_S501_REFERENCE,
            "tcvn4054": TCVN_REFERENCE,
            "user_profile": PROFILE_ID,
            "qcvn_search_evidence": c.qcvn_search_evidence,
        },
        "notes": [
            "QCVN C.7(d) limits an all-W.207 dense sequence to W.207d or W.207e.",
            "W.205 or mixed-family grouping is user-approved project practice, not quoted as QCVN text.",
            "S.501 length follows the user's rule from sign position to the last junction and is rounded per Annex F.1.",
            "Actual sight obstruction remains a field/profile verification; Table 10 is only the minimum design value.",
        ],
        "pending_checks": ["actual_forward_visibility", "priority_and_branch_topology",
                           "native_station_geometry", "roadside_clearance_and_obstruction",
                           "asset_geometry_review", "independent_design_review", "CAD_readback"],
    }


def sign_context_from_dict(data: dict) -> SignPositionContext:
    data = dict(data)
    for name in ("alignment_start_m", "alignment_end_m", "target_station_m", "qcvn_distance_m"):
        if data.get(name) is not None:
            if isinstance(data[name], bool):
                raise ValueError(f"{name} must be a decimal in metres")
            data[name] = D(str(data[name]))
    return SignPositionContext(**data)


def junction_context_from_dict(data: dict) -> JunctionWarningContext:
    data = dict(data)
    for name in ("alignment_start_m", "alignment_end_m"):
        if isinstance(data.get(name), bool):
            raise ValueError(f"{name} must be a decimal in metres")
        data[name] = D(str(data[name]))
    junctions = []
    for raw in data["junctions"]:
        item = dict(raw)
        if isinstance(item.get("station_m"), bool):
            raise ValueError("station_m must be a decimal in metres")
        item["station_m"] = D(str(item["station_m"]))
        junctions.append(Junction(**item))
    data["junctions"] = tuple(junctions)
    return JunctionWarningContext(**data)
