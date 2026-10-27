"""Guarded adapter to the user's existing simple-box 4.4 classification skill."""
import math
from copy import deepcopy
from .skill44_classifier import classify_intersections


def propose_boxes(branches: list[dict], *, snapshot_id: str, road_type: str,
                  application_evidence: str | None, native_curve_distances_verified: bool,
                  constant_width_verified: bool, physical_median_present: bool | None,
                  width_m: float = 0.20) -> dict:
    """One independently reviewed junction/group at a time, never a live query.

    minS/maxS/midS are native curve distances, NOT displayed Civil chainage.
    Widths are measured per side. Variable-width/median layouts need a separate
    geometry design; they must not inherit the legacy two-lane rectangle rule.
    """
    issues = []
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        issues.append("missing_snapshot")
    if road_type != "ordinary" or physical_median_present is not False:
        issues.append("requires_carriageway_specific_median_design")
    if not isinstance(application_evidence, str) or not application_evidence.strip():
        issues.append("missing_4_4_application_evidence")
    if native_curve_distances_verified is not True:
        issues.append("native_curve_distances_unverified")
    if constant_width_verified is not True:
        issues.append("variable_or_unverified_width_requires_geometry_design")
    if isinstance(width_m, bool) or not math.isfinite(width_m) or not .20 <= width_m <= .40:
        issues.append("simple_box_width_outside_qcvn")
    seen = set()
    valid = bool(branches)
    for b in branches:
        identity = (b.get("timHandle"), b.get("handle"))
        numeric = all(isinstance(b.get(k), (int, float)) and not isinstance(b.get(k), bool)
                      and math.isfinite(b[k]) for k in ("minS", "maxS", "midS", "avgW"))
        if (not all(isinstance(x, str) and x.strip() for x in identity) or identity in seen
                or b.get("side") not in {"LEFT", "RIGHT"} or not numeric):
            valid = False
        elif not 0 <= b["minS"] <= b["midS"] <= b["maxS"] or b["minS"] == b["maxS"] or b["avgW"] <= 0:
            valid = False
        if all(isinstance(x, str) for x in identity):
            seen.add(identity)
    if not valid:
        issues.append("invalid_or_duplicate_branch_measurements")
    else:
        # Legacy nearest-neighbour pairing is ambiguous with multiple nearby
        # opposite mouths. Do not let list order silently decide the design.
        for a in branches:
            opposites = [b for b in branches if a["timHandle"] == b["timHandle"]
                         and a["side"] != b["side"] and abs(a["midS"] - b["midS"]) <= 30]
            if len(opposites) > 1:
                issues.append("ambiguous_opposite_branch_pairing")
                break
    boxes = [] if issues else classify_intersections(deepcopy(branches), delta_threshold=5.0,
                                                     max_pair_dist=30.0, default_lane_w=0.0)
    return {"schema_version": 1, "marking_code": "4.4", "variant": "simple",
            "status": "blocked" if issues else "proposed", "issues": issues,
            "cad_execution_allowed": False, "snapshot_id": snapshot_id, "boxes": boxes,
            "appearance": {"color_aci": 2, "width_m": width_m, "linetype": "Continuous",
                           "layer_candidate": "vach 4.4", "entity_recipe": "closed outline + 2 diagonals"},
            "basis": {"classification": "user skill ve-vach-son-mac-vong-4-4-qcvn41-2024",
                      "threshold_status": "project_practice", "direct_pair_limit_m": 5,
                      "staggered_pair_limit_m": 30,
                      "qcvn": "QCVN 41:2024, G1.4(e), PDF pages 177-178, figures G.38-G.39",
                      "application": application_evidence},
            "pending_checks": ["native_curve_geometry", "paint_envelope_within_pavement",
                               "curve_distance_to_alignment_station_mapping", "approved_DWG_style_mapping",
                               "owned_entities_only_update", "CAD_readback", "paint_union_area"]}
