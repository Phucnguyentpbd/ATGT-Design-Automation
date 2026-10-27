from dataclasses import replace
from decimal import Decimal as D

import pytest

from atgt.sign_placement_rules import (
    Junction,
    JunctionWarningContext,
    SignPositionContext,
    STOPPING_SIGHT_DISTANCE_M,
    propose_junction_warnings,
    propose_sign_position,
)


@pytest.fixture
def sign():
    return SignPositionContext(
        "snapshot", "alignment", "hazard-1", "W.201a", "ordinary", "increasing", 60,
        D("0"), D("1000"), D("500"), "QCVN search page 25 and applicable annex",
        True,
    )


@pytest.mark.parametrize("speed,sight", sorted(STOPPING_SIGHT_DISTANCE_M.items()))
def test_tcvn4054_table10_fallback_uses_design_speed_after_qcvn_search(sign, speed, sight):
    result = propose_sign_position(replace(sign, design_speed_kmh=speed), tcvn_source_verified=True)
    assert result["status"] == "proposed"
    assert D(result["distance_before_target_m"]) == sight
    assert D(result["placement_station_m"]) == D("500") - sight
    assert result["basis"]["kind"] == "tcvn4054_stopping_sight_distance_fallback"


def test_explicit_qcvn_position_takes_precedence_over_stopping_sight_distance(sign):
    result = propose_sign_position(replace(
        sign, qcvn_no_numeric_distance_confirmed=False, qcvn_distance_m=D("25"),
        qcvn_distance_reference="QCVN applicable sign clause, reviewed PDF page"),
        tcvn_source_verified=False)
    assert result["status"] == "proposed"
    assert result["distance_before_target_m"] == "25"
    assert result["placement_station_m"] == "475"
    assert result["basis"]["kind"] == "qcvn_explicit_position"


@pytest.mark.parametrize("change,reason", [
    ({"qcvn_no_numeric_distance_confirmed": False}, "qcvn_numeric_distance_status_unresolved"),
    ({"design_speed_kmh": 50}, "design_speed_not_in_tcvn4054_table10"),
    ({"travel_direction": "sideways"}, "invalid_travel_direction"),
])
def test_sign_fallback_blocks_unresolved_or_unsupported_inputs(sign, change, reason):
    result = propose_sign_position(replace(sign, **change), tcvn_source_verified=True)
    assert result["status"] == "blocked" and result["placement_station_m"] is None
    assert reason in result["issues"]


def test_sign_fallback_requires_locked_tcvn_source(sign):
    result = propose_sign_position(sign, tcvn_source_verified=False)
    assert result["status"] == "blocked"
    assert "tcvn4054_source_not_configured_or_verified" in result["issues"]


def _junction(junction_id, station, relationship, code, side="right"):
    return Junction(junction_id, D(str(station)), relationship, code, side,
                    f"native geometry {junction_id}", f"approved priority {junction_id}")


def _corridor(*junctions, direction="increasing", speed=60):
    return JunctionWarningContext(
        "snapshot", "alignment", "ordinary", direction, speed, D("0"), D("1000"),
        "QCVN pages 25, 100, 101 and 151 reviewed", tuple(junctions),
    )


def test_dense_nonpriority_sequence_uses_qcvn_w207d_and_s501_to_last_junction():
    context = _corridor(
        _junction("J1", 300, "side_road_non_priority", "W.207b", "right"),
        _junction("J2", 350, "side_road_non_priority", "W.207c", "left"),
    )
    result = propose_junction_warnings(context, tcvn_source_verified=True)
    placement = result["placements"][0]
    assert result["status"] == "proposed" and len(result["placements"]) == 1
    assert placement["representative_sign_code"] == "W.207d"
    assert placement["placement_station_m"] == "225"
    assert placement["s501_required"] and placement["s501_length_m"] == "130"
    assert placement["rule_kind"] == "qcvn_w207_dense_sequence"


def test_mixed_dense_sequence_retains_actual_family_of_nearest_junction():
    context = _corridor(
        _junction("J1", 300, "equal", "W.205b", "both"),
        _junction("J2", 340, "side_road_non_priority", "W.207c", "left"),
    )
    result = propose_junction_warnings(context, tcvn_source_verified=True)
    placement = result["placements"][0]
    assert placement["representative_sign_code"] == "W.205b"
    assert placement["nearest_junction_priority_relationship"] == "equal"
    assert placement["s501_length_m"] == "120"
    assert placement["rule_kind"] == "user_approved_cluster_retains_nearest_junction_family"


def test_gap_equal_to_sight_distance_remains_two_independent_warnings():
    context = _corridor(
        _junction("J1", 300, "equal", "W.205a", "both"),
        _junction("J2", 375, "equal", "W.205a", "both"),
    )
    result = propose_junction_warnings(context, tcvn_source_verified=True)
    assert len(result["placements"]) == 2
    assert all(not p["s501_required"] for p in result["placements"])


def test_priority_relationship_cannot_be_mismatched_to_sign_family():
    context = _corridor(_junction("J1", 300, "equal", "W.207b"))
    result = propose_junction_warnings(context, tcvn_source_verified=True)
    assert result["status"] == "blocked" and not result["placements"]
    assert "J1:equal_priority_requires_w205_variant" in result["issues"]
