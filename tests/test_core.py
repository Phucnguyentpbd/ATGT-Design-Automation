from decimal import Decimal as D
import pytest
from atgt.contracts import SignFace, Marking, ProjectContext, RoadSegment
from atgt.validation import validate_sign_code, validate_project
from atgt.takeoff import sign_summary, painted_area, segment_area, ledger_for_markings

def test_sign_prefix_and_special_codes():
    for code in ("P.102", "W.201a", "R.420", "DP.135", "S.501", "IE.123", "R.E,9a"):
        assert validate_sign_code(code)
    assert not validate_sign_code("102")

def test_count_faces_not_posts():
    f = lambda n: SignFace(str(n), "one-cluster", "P.102", "circle", D(700), D(700), "install", "asset", "verified", "QCVN")
    assert sum(sign_summary([f(1), f(2), f(3)]).values()) == 3

def test_paint_clipping_conserves_area():
    m = Marking("1", "V.1", "road", D(0), D(12), D("0.15"), D(2), ((D(1), D(3)), (D(7), D(10))), "verified", "snap")
    assert painted_area(m) == D("0.75")
    assert sum(segment_area(m, [(D(0), D(8)), (D(8), D(12))])) == painted_area(m)

def test_stale_snapshot_is_missing_not_zero():
    m = Marking("1", "V.1", "road", D(0), D(3), D("0.2"), D(2), ((D(0), D(3)),), "verified", "old")
    rec = ledger_for_markings([m], "new")[0]
    assert rec.quantity is None and rec.issue == "stale snapshot"

def test_duplicate_object_rejected():
    m = Marking("1", "V.1", "road", D(0), D(1), D("0.1"), D(2), ((D(0), D(1)),), "verified", "s")
    with pytest.raises(ValueError):
        ledger_for_markings([m, m], "s")

def test_road_scope_is_fail_closed():
    c = ProjectContext("p", (), (RoadSegment("s", "expressway", D(0), D(100), "A"),), None)
    codes = {i.code for i in validate_project(c)}
    assert {"unsupported_road_type", "missing_direction", "missing_sources", "missing_snapshot"} <= codes
