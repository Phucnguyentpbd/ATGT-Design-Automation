import hashlib

from atgt.assets import scan_dwg_library
from atgt.library_review import make_review_queue, review_flags, validate_against_lock


def _fixture(tmp_path):
    (tmp_path / "Bien_Cam").mkdir()
    (tmp_path / "Bien_Chi_Dan").mkdir()
    (tmp_path / "Bien_Cam" / "135.dwg").write_bytes(b"AC1021" + b"cam")
    (tmp_path / "Bien_Chi_Dan" / "420.dwg").write_bytes(b"AC1021" + b"guide")
    catalog = scan_dwg_library(tmp_path)
    locked = {"inventory": {"total_dwg": 2, "total_bytes": catalog["total_bytes"],
             "by_group": {"Bien_Cam": 1, "Bien_Chi_Dan": 1}, "header": "AC1021"}}
    return catalog, locked


def test_real_exception_cases_are_flagged_without_mapping():
    assert "crosscheck_DP.135" in review_flags("Bien_Cam/135.dwg")
    assert "crosscheck_R.420" in review_flags("Bien_Chi_Dan/420.dwg")
    assert "special_family_identifier" in review_flags("Bien_Hieu_Lenh/E9A.dwg")
    assert "legacy_variant_suffix" in review_flags("Bien_Cam/124A-1.dwg")
    assert "filename_missing_canonical_prefix" in review_flags("Bien_Cam/102.dwg")


def test_fingerprints_and_review_queue_are_fail_closed(tmp_path):
    catalog, locked = _fixture(tmp_path)
    assert validate_against_lock(catalog, locked) == []
    queue = make_review_queue(catalog)
    assert len(queue) == 2
    assert all(not q["geometry_verified"] for q in queue)
    assert all(q["sign_code"] is None for q in queue)


def test_mismatch_does_not_silently_pass(tmp_path):
    catalog, locked = _fixture(tmp_path)
    locked["inventory"]["total_bytes"] += 1
    issues = validate_against_lock(catalog, locked)
    assert any("total bytes" in issue for issue in issues)
    catalog["assets"][0]["dwg_header"] = "UNKNOWN"
    issues = validate_against_lock(catalog, locked)
    assert any("unexpected header" in issue for issue in issues)


def test_detects_duplicate_asset_paths(tmp_path):
    catalog, locked = _fixture(tmp_path)
    catalog["assets"][0]["relative_path"] = catalog["assets"][1]["relative_path"]
    assert "duplicate relative paths" in validate_against_lock(catalog, locked)
