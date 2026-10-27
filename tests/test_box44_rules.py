import pytest
from atgt.box44_rules import propose_boxes


def branch(handle, side, mid, width=2.8):
    return {"handle": handle, "timHandle": "C1", "side": side,
            "minS": mid - 2, "midS": mid, "maxS": mid + 2, "avgW": width}


def plan(branches, **overrides):
    args = dict(snapshot_id="s", road_type="ordinary", application_evidence="approved no-stop area",
                native_curve_distances_verified=True, constant_width_verified=True, physical_median_present=False)
    return propose_boxes(branches, **{**args, **overrides})


@pytest.mark.parametrize("delta,kinds", [
    (5.0, ["NGA_TU_TRUC_DIEN"]),
    (5.01, ["NGA_TU_LECH_NHIEU_LEFT", "NGA_TU_LECH_NHIEU_RIGHT"]),
    (30.0, ["NGA_TU_LECH_NHIEU_LEFT", "NGA_TU_LECH_NHIEU_RIGHT"]),
    (30.01, ["NGA_3_LEFT", "NGA_3_RIGHT"]),
])
def test_reused_skill_preserves_three_cases_and_boundaries(delta, kinds):
    result = plan([branch("a", "LEFT", 20), branch("b", "RIGHT", 20 + delta)])
    assert result["status"] == "proposed"
    assert [b["type"] for b in result["boxes"]] == kinds
    assert not result["cad_execution_allowed"]


def test_measured_width_is_not_inflated_to_legacy_default():
    result = plan([branch("a", "LEFT", 20)])
    assert result["boxes"][0]["w"] == 2.8


@pytest.mark.parametrize("overrides,reason", [
    ({"application_evidence": None}, "missing_4_4_application_evidence"),
    ({"physical_median_present": True}, "requires_carriageway_specific_median_design"),
    ({"road_type": "divided_rural"}, "requires_carriageway_specific_median_design"),
    ({"constant_width_verified": False}, "variable_or_unverified_width_requires_geometry_design"),
    ({"native_curve_distances_verified": False}, "native_curve_distances_unverified"),
    ({"width_m": .15}, "simple_box_width_outside_qcvn"),
])
def test_inapplicable_or_unverified_junction_does_not_produce_boxes(overrides, reason):
    result = plan([branch("a", "LEFT", 20)], **overrides)
    assert result["status"] == "blocked" and result["boxes"] == []
    assert reason in result["issues"]


def test_ambiguous_pairing_cannot_depend_on_input_order():
    branches = [branch("a", "LEFT", 20), branch("b", "RIGHT", 22), branch("c", "RIGHT", 25)]
    for items in (branches, list(reversed(branches))):
        assert "ambiguous_opposite_branch_pairing" in plan(items)["issues"]
