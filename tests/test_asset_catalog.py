import hashlib
import json

import pytest

from atgt.asset_catalog import AssetCatalog


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def asset(asset_id, kind, code, source, relative, source_hash, mode,
          source_block, target_block, status="approved_for_insert"):
    return {
        "asset_id": asset_id, "kind": kind, "code": code, "source": source,
        "source_relative_path": relative, "source_sha256": source_hash,
        "import_mode": mode, "source_block_name": source_block,
        "target_block_name": target_block, "source_units": "Meters",
        "placement_scale": 1.0, "rotation_offset_rad": 0.0,
        "extents_size": [1.0, 3.0, 0.0], "status": status,
        "geometry_verified": status == "approved_for_insert",
        "units_verified": status == "approved_for_insert",
        "review_evidence": "fixture geometry and units review",
    }


def test_catalog_owns_approval_path_containment_and_source_hash(tmp_path):
    signs = tmp_path / "signs"
    sign = signs / "Bien_Cam" / "102.dwg"
    sign.parent.mkdir(parents=True)
    sign.write_bytes(b"reviewed sign")
    template = tmp_path / "template.dwg"
    template.write_bytes(b"reviewed marking template")
    catalog_path = tmp_path / "assets.json"
    catalog_path.write_text(json.dumps({
        "schema_version": 1, "catalog_id": "ATGT-ASSETS-TEST-V1",
        "assets": [
            asset("sign:P.102:v1", "sign", "P.102", "sign_library",
                  "Bien_Cam/102.dwg", digest(sign), "whole_dwg_as_block", None,
                  "ATGT_SIGN_P_102_V1"),
            asset("marking:7.6:3m:v1", "marking_block", "7.6", "marking_template",
                  "template.dwg", digest(template), "named_block",
                  "VS_7.6_HINH_THOI_3M", "VS_7.6_HINH_THOI_3M"),
        ]}), encoding="utf-8")

    catalog = AssetCatalog(catalog_path, signs, template)
    assert catalog.summary()["status_counts"]["approved_for_insert"] == 2
    assert catalog.list(code="P.102")["items"][0]["asset_id"] == "sign:P.102:v1"
    assert catalog.source_path(catalog.get("sign:P.102:v1", require_approved=True)) == sign

    sign.write_bytes(b"changed after approval")
    with pytest.raises(ValueError, match="checksum mismatch"):
        catalog.get("sign:P.102:v1", require_approved=True)


def test_catalog_rejects_unapproved_or_escaping_asset(tmp_path):
    signs = tmp_path / "signs"
    signs.mkdir()
    template = tmp_path / "template.dwg"
    template.write_bytes(b"template")
    outside = tmp_path / "outside.dwg"
    outside.write_bytes(b"outside")
    catalog_path = tmp_path / "assets.json"
    review = asset("sign:P.102:review", "sign", "P.102", "sign_library",
                   "102.dwg", digest(outside), "whole_dwg_as_block", None,
                   "ATGT_SIGN_P_102_REVIEW", status="review_required")
    catalog_path.write_text(json.dumps({"schema_version": 1,
        "catalog_id": "ATGT-ASSETS-TEST-V1", "assets": [review]}), encoding="utf-8")
    catalog = AssetCatalog(catalog_path, signs, template)
    with pytest.raises(ValueError, match="not approved_for_insert"):
        catalog.get("sign:P.102:review", require_approved=True)

    review["source_relative_path"] = "../outside.dwg"
    catalog_path.write_text(json.dumps({"schema_version": 1,
        "catalog_id": "ATGT-ASSETS-TEST-V2", "assets": [review]}), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes"):
        AssetCatalog(catalog_path, signs, template)
