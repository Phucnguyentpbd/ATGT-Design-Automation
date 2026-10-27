from copy import deepcopy
import pytest
from atgt.export_plan import build_export_plan, station_label


@pytest.fixture
def ledger():
    return {"schema_version":1,"data_kind":"synthetic",
            "project":{"id":"demo","title":"DỮ LIỆU GIẢ ĐỊNH"},
            "snapshot":{"id":"s","readback_verified":True,"evidence":"synthetic test readback"},
            "sign_coverage_complete":True,
            "segments":[{"id":"s1","alignment_id":"T1","start_m":"0","end_m":"1000","label":"Km0–Km1"}],
            "coverage":[{"segment_id":"s1","item_code":"3.1a","thickness_mm":"2","complete":True,"evidence":"synthetic full coverage"}],
            "quantities":[{"measurement_id":"m1","object_id":"o1","segment_id":"s1","item_code":"3.1a","thickness_mm":"2",
                           "quantity":"20","unit":"m2","measurement_method":"actual_painted_area","status":"verified","source_snapshot_id":"s","evidence":"synthetic"}],
            "clusters":[{"cluster_id":"c1","alignment_id":"T1","alignment_label":"Tuyến 1","station_m":"100","side":"right"}],
            "faces":[{"face_id":f"f{i}","cluster_id":"c1","sign_code":"P.102","shape":"circle","width_mm":"700","height_mm":"700",
                      "work":"install","asset_id":"synthetic-asset","status":"verified","source_snapshot_id":"s","reference":"synthetic","evidence":"synthetic"} for i in range(4)]}


def values(spec):
    return {entry["range"]:entry["values"][0] for entry in spec["values"]}


def test_measured_zero_and_missing_coverage_remain_distinct(ledger):
    result = build_export_plan(ledger)
    cells = values(result["sheets"][0])
    assert cells["F11"] == [20.0]
    assert cells["F12"] == ["Chưa đo đủ"]
    empty = deepcopy(ledger); empty["quantities"] = []
    assert values(build_export_plan(empty)["sheets"][0])["F11"] == [0.0]


def test_four_faces_continue_on_next_row_and_pole_does_not_change_summary(ledger):
    a = build_export_plan(ledger,{"c1":"Cột do người dùng nhập"})
    b = build_export_plan(ledger,{"c1":"Phân loại khác"})
    cells = values(a["sheets"][1])
    assert cells["A8"][16] == cells["A9"][16] == "c1"
    assert cells["A8"][14] == "Cột do người dùng nhập" and cells["A9"][14] is None
    assert cells["A8"][5] == cells["A8"][8] == cells["A8"][11] == cells["A9"][5] == "P.102"
    assert a["expected"] == b["expected"]
    assert a["expected"]["summary_counts"][0]["quantity"] == 4
    assert "$O$" not in a["sheets"][1]["formulas"][0]["formulas"][0][0]


@pytest.mark.parametrize("mutate,reason", [
    (lambda d:d["faces"][0].update(source_snapshot_id="old"),"stale"),
    (lambda d:d["quantities"].append(deepcopy(d["quantities"][0])),"Duplicate"),
    (lambda d:d["quantities"][0].update(unit="m"),"unit"),
    (lambda d:d["quantities"][0].update(measurement_method="measured_paving_area"),"method"),
    (lambda d:d["quantities"][0].update(item_code="4.4"),"union"),
    (lambda d:d["snapshot"].update(readback_verified=False),"readback"),
    (lambda d:d.update(sign_coverage_complete=False),"coverage"),
])
def test_unverified_or_mismatched_quantities_cannot_reach_writer(ledger, mutate, reason):
    mutate(ledger)
    with pytest.raises(ValueError,match=reason): build_export_plan(ledger)


def test_more_segments_extend_the_template_total_column(ledger):
    ledger["segments"] += [{"id":f"s{i}","alignment_id":"T1","start_m":str((i-1)*1000),"end_m":str(i*1000),"label":f"Đoạn {i}"} for i in (2,3,4)]
    sheet = build_export_plan(ledger)["sheets"][0]
    assert sheet["print_area"] == "A1:J30"
    assert next(x for x in sheet["formulas"] if x["range"] == "J11")["formulas"] == [['=IF(COUNT(F11:I11)=4,SUM(F11:I11),"Chưa đủ")']]


def test_station_rounding_carries_into_next_kilometre():
    assert station_label("999.999") == "Km1+000.00"


def test_removed_cluster_does_not_silently_drop_manual_classification(ledger):
    with pytest.raises(ValueError, match="manual.*cluster"):
        build_export_plan(ledger, {"removed-cluster": "Manual classification"})
