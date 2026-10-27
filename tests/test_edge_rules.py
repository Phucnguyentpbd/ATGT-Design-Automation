from dataclasses import replace
from decimal import Decimal as D
import pytest
from atgt.edge_rules import EdgeContext, propose_edge_marking, context_from_dict
from atgt.linetypes import parse_lin


@pytest.fixture
def patterns(tmp_path):
    path = tmp_path / "source.lin"
    path.write_text("*VACH_3.1B_0.6M, source\nA,.6,-.6\n*VACH_3.1B_1.0M, source\nA,1,-1\n")
    return parse_lin(path)


@pytest.fixture
def edge():
    return EdgeContext("snapshot", "alignment", "A1", "ordinary", "outer_pavement", "continuous",
                       D(0), D(100), D("0.20"), D(7), D(3.5), "survey", "approved traffic plan", True)


@pytest.mark.parametrize("width,clearance", [("0.15", "0.225"), ("0.20", "0.20")])
def test_centerline_offset_converts_to_outside_paint_clearance(edge, patterns, width, clearance):
    result = propose_edge_marking(replace(edge, width_m=D(width)), patterns)
    assert result["status"] == "proposed" and result["marking_code"] == "3.1a"
    assert D(result["centerline_offset_m"]) == D("0.3")
    assert D(result["outside_paint_clearance_m"]) == D(clearance)
    assert not result["cad_execution_allowed"]


def test_median_opening_uses_user_offset_and_only_06_pattern(edge, patterns):
    c = replace(edge, road_type="divided_rural", edge_role="median", scenario="median_opening",
                turning_permitted=True, movement_evidence="approved movement M1")
    result = propose_edge_marking(c, patterns)
    assert result["status"] == "proposed" and result["marking_code"] == "3.1b"
    assert result["centerline_offset_m"] == "0.50"
    assert result["linetype"] == "VACH_3.1B_0.6M"
    assert result["basis"]["offset"]["kind"] == "user_project_practice"


@pytest.mark.parametrize("change,reason", [
    ({"scenario": "local_access"}, "turning_permission_not_confirmed"),
    ({"road_type": "urban"}, "unsupported_road_type"),
    ({"outer_edge_matches_running_edge": None}, "outer_pavement_vs_running_edge_unresolved"),
    ({"width_m": D("0.3")}, "width_outside_qcvn_3_1"),
    ({"width_m": D("NaN")}, "invalid_numeric_input"),
    ({"carriageway_width_m": D(6)}, "under_7m_requires_necessity_evidence"),
    ({"available_paved_width_m": D("0.35")}, "paint_outside_available_pavement"),
    ({"snapshot_id": ""}, "missing_snapshot_id"),
    ({"scenario": "merge_diverge"}, "scenario_requires_other_rule"),
])
def test_uncertain_or_inapplicable_context_blocks(edge, patterns, change, reason):
    result = propose_edge_marking(replace(edge, **change), patterns)
    assert result["status"] == "blocked" and result["marking_code"] is None
    assert reason in result["issues"]


def test_wrong_dash_pattern_is_not_substituted(edge, patterns):
    c = replace(edge, scenario="local_access", turning_permitted=True, movement_evidence="movement plan")
    result = propose_edge_marking(c, patterns[1:])
    assert "missing_or_ambiguous_3_1b_0_6_pattern" in result["issues"]


def test_string_boolean_cannot_authorize_turning():
    with pytest.raises(ValueError, match="turning_permitted"):
        context_from_dict({"start_m": "0", "end_m": "1", "width_m": "0.2", "carriageway_width_m": "7",
                           "available_paved_width_m": "3", "turning_permitted": "false"})
