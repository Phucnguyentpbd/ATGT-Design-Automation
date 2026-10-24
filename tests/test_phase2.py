from decimal import Decimal as D
import pytest
from atgt.assets import scan_dwg_library, candidate_code
from atgt.linetypes import parse_lin, pattern_manifest
from atgt.knowledge import RuleStore


def test_candidate_prefix_does_not_auto_approve():
    assert candidate_code("102") is None
    assert candidate_code("P.102") == "P.102"
    assert candidate_code("R.420_sizeA") == "R.420"


def test_catalog_stable_ids_and_grouping(tmp_path):
    folder = tmp_path / "Bien_Cam"
    folder.mkdir()
    (folder / "102.dwg").write_bytes(b"AC1021source")
    (folder / "P.102.dwg").write_bytes(b"AC1021other")
    result = scan_dwg_library(tmp_path)
    assert result["total_dwg"] == 2
    assert result["by_group"] == {"Bien_Cam": 2}
    assert all(a["status"] == "unverified" and not a["geometry_verified"] for a in result["assets"])
    assert result["assets"][0]["asset_id"] != result["assets"][1]["asset_id"]


def test_catalog_no_library_is_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan_dwg_library(tmp_path / "missing")


def test_lin_parsing_and_nominal_lengths(tmp_path):
    path = tmp_path / "sample.lin"
    path.write_text(";; comment\n*VACH_1.1, Marking\nA,1.0,-3.0\n", encoding="utf-8")
    items = parse_lin(path)
    assert len(items) == 1
    assert items[0].status == "unverified"
    assert items[0].nominal_cycle_m == D(4)
    assert items[0].nominal_paint_m == D(1)
    assert pattern_manifest(path)["count"] == 1


def test_lin_rejects_complex_definition(tmp_path):
    path = tmp_path / "complex.lin"
    path.write_text("*A, complex\nA,1.0,[MYSHAPE],-2.0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_lin(path)


def test_knowledge_requires_explicit_approval(tmp_path):
    db = RuleStore(tmp_path / "knowledge.sqlite")
    db.add_draft("TABLE2-GROUP", 1, "a" * 64, "QCVN 41:2024 p14/table 2", ("ordinary",), {"factor": "1.25"})
    assert db.executable("ordinary") == []
    with pytest.raises(ValueError):
        db.approve("TABLE2-GROUP", 1, "Engineer", source_checked=False)
    db.approve("TABLE2-GROUP", 1, "Engineer", source_checked=True)
    assert db.executable("ordinary")[0].payload["factor"] == "1.25"
    assert db.executable("expressway") == []
    assert db.search("TABLE2", include_drafts=False)[0].reviewer == "Engineer"
    with pytest.raises(ValueError):
        db.add_draft("TABLE2-GROUP", 1, "a" * 64, "overwrite", ("ordinary",), {})
    db.close()
