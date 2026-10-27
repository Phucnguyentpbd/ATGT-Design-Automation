import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from atgt.cad_session import CadConfig, CadSessionService


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configured_service(tmp_path, source, output, rpc):
    sign_library = tmp_path / "sign-library"
    sign = sign_library / "Bien_Cam" / "102.dwg"
    sign.parent.mkdir(parents=True, exist_ok=True)
    sign.write_bytes(b"fixture sign P.102")
    template = tmp_path / "marking-template.dwg"
    template.write_bytes(b"fixture marking template")
    catalog = tmp_path / "asset-catalog.json"
    catalog.write_text(json.dumps({
        "schema_version": 1, "catalog_id": "ATGT-ASSETS-TEST-V1", "assets": [
            {"asset_id": "sign:P.102:v1", "kind": "sign", "code": "P.102",
             "source": "sign_library", "source_relative_path": "Bien_Cam/102.dwg",
             "source_sha256": digest(sign), "import_mode": "whole_dwg_as_block",
             "source_block_name": None, "target_block_name": "ATGT_SIGN_P_102_V1",
             "source_units": "Meters", "placement_scale": 1.0,
             "rotation_offset_rad": 0.0, "extents_size": [0.7, 0.7, 0.01],
             "status": "approved_for_insert", "geometry_verified": True,
             "units_verified": True, "review_evidence": "fixture sign review"},
            {"asset_id": "marking:7.6:3m:v1", "kind": "marking_block", "code": "7.6",
             "source": "marking_template", "source_relative_path": "marking-template.dwg",
             "source_sha256": digest(template), "import_mode": "named_block",
             "source_block_name": "VS_7.6_HINH_THOI_3M",
             "target_block_name": "VS_7.6_HINH_THOI_3M", "source_units": "Meters",
             "placement_scale": 1.0, "rotation_offset_rad": 0.0,
             "extents_size": [1.0, 3.0, 0.0], "status": "approved_for_insert",
             "geometry_verified": True, "units_verified": True,
             "review_evidence": "fixture marking review"}
        ]}), encoding="utf-8")
    rpc.asset_hashes = {"sign:P.102:v1": digest(sign),
                        "marking:7.6:3m:v1": digest(template)}
    return CadSessionService(CadConfig(source, output, template, sign_library, catalog), rpc)


class FakeRpc:
    def __init__(self, source: Path, work_copy: Path):
        self.active = source
        self.source = source
        self.work_copy = work_copy
        self.execute_descriptions = []
        self.readback = []
        self.imported_assets = []
        self.asset_hashes = {}
        self.work_copy_units = "Meters"

    async def health(self):
        return {"connected": True, "drawingName": str(self.active)}

    async def query(self, code):
        if "ATGT_ASSET_IMPORT_VERIFY_V1" in code:
            return self.imported_assets
        if "GetXDataForApplication" in code:
            return self.readback
        if "ATGT_LAYER_INVENTORY_V1" in code:
            return {"filename": str(self.active), "dbmod": 21, "insunits": "Meters",
                    "total_entities": 12, "total_groups": 3, "returned_groups": 2,
                    "groups": [
                        {"layer": "TIM_DUONG", "type": "LWPOLYLINE", "count": 4,
                         "linetypes": ["Continuous"], "colors": [1], "closed_count": 0,
                         "sample_handles": ["A1", "A2"], "extmin": [0, 0, 0], "extmax": [10, 20, 0]},
                        {"layer": "MEP_VIA", "type": "LINE", "count": 3,
                         "linetypes": ["Continuous"], "colors": [2], "closed_count": 0,
                         "sample_handles": ["B1"], "extmin": [0, 0, 0], "extmax": [10, 20, 0]},
                    ]}
        if "ATGT_DECLARED_LAYER_SURVEY_V1" in code:
            return {"filename": str(self.active), "dbmod": 21, "insunits": "Meters",
                    "declared_layers": [
                        {"role": "centerline", "layer": "DO"},
                        {"role": "road_edge", "layer": "mepduong"}],
                    "missing_layers": [], "empty_layers": [], "total_entities": 3,
                    "offset": 0, "limit": 100,
                    "entities": [
                        {"role": "centerline", "layer": "DO", "handle": "C1",
                         "type": "LWPOLYLINE", "geometry_mode": "exact_polyline",
                         "length": 100.0, "vertex_count": 3, "closed": False,
                         "linetype": "ByLayer", "color": 1,
                         "extmin": [0, 0, 0], "extmax": [100, 0, 0]},
                        {"role": "road_edge", "layer": "mepduong", "handle": "E1",
                         "type": "LWPOLYLINE", "geometry_mode": "exact_polyline",
                         "length": 100.0, "vertex_count": 3, "closed": False,
                         "linetype": "ByLayer", "color": 2,
                         "extmin": [0, -3.5, 0], "extmax": [100, -3.5, 0]},
                        {"role": "road_edge", "layer": "mepduong", "handle": "E2",
                         "type": "LWPOLYLINE", "geometry_mode": "exact_polyline",
                         "length": 100.0, "vertex_count": 3, "closed": False,
                         "linetype": "ByLayer", "color": 2,
                         "extmin": [0, 3.5, 0], "extmax": [100, 3.5, 0]}],
                    "layer_counts": [
                        {"layer": "DO", "role": "centerline", "count": 1, "supported": 1},
                        {"layer": "mepduong", "role": "road_edge", "count": 2, "supported": 2}]}
        if "ATGT_NATIVE_GEOMETRY_V1" in code:
            requested = [value.upper() for value in __import__("re").findall(r'"([0-9A-Fa-f]+)"', code.split("var rows=", 1)[0])]
            return {"filename": str(self.active), "dbmod": 21, "insunits": "Meters",
                    "entities": [{"handle": value, "type": "LINE", "layer": "TIM_DUONG",
                                  "linetype": "Continuous", "color": 1,
                                  "representation": "line_endpoints", "start": [0, 0, 0],
                                  "end": [10, 0, 0], "length": 10.0,
                                  "exact_marking_geometry": True} for value in requested]}
        units = self.work_copy_units if self.active == self.work_copy else "Meters"
        return {"document": str(self.active), "filename": str(self.active), "dbmod": 21,
                "insunits": units, "measurement": "English", "object_count": 6619,
                "extmin": [0, 0, 0], "extmax": [10, 20, 0]}

    async def execute(self, code, description):
        self.execute_descriptions.append(description)
        if description.startswith("Create an isolated"):
            self.work_copy.parent.mkdir(parents=True, exist_ok=True)
            self.work_copy.write_bytes(b"synthetic dwg snapshot")
            return {"source": str(self.source), "target": str(self.work_copy)}
        if description.startswith("Open and activate"):
            self.active = self.work_copy
            return {"document": str(self.work_copy)}
        if description.startswith("Normalize the isolated"):
            self.work_copy_units = "Meters"
            return {"filename": str(self.work_copy), "insunits": "Meters"}
        if description.startswith("Import the reviewed"):
            return {"name": "VACH_3.1B_0.6M", "existed": False,
                    "patternLength": 1.2, "dashes": [0.6, -0.6], "target_insunits": "Meters"}
        if description.startswith("ATGT guarded asset import"):
            rows = []
            if "sign:P.102:v1" in code:
                rows.append({"target_block_name": "ATGT_SIGN_P_102_V1", "found": True,
                             "asset_id": "sign:P.102:v1", "source_sha256": self.asset_hashes["sign:P.102:v1"],
                             "code": "P.102", "kind": "sign", "import_id": description.rsplit(" ", 1)[-1],
                             "entity_count": 7})
            if "marking:7.6:3m:v1" in code:
                rows.append({"target_block_name": "VS_7.6_HINH_THOI_3M", "found": True,
                             "asset_id": "marking:7.6:3m:v1", "source_sha256": self.asset_hashes["marking:7.6:3m:v1"],
                             "code": "7.6", "kind": "marking_block", "import_id": description.rsplit(" ", 1)[-1],
                             "entity_count": 1})
            self.imported_assets = rows
            return {"import_id": description.rsplit(" ", 1)[-1],
                    "assets": [{"asset_id": row["asset_id"], "target_block_name": row["target_block_name"]}
                               for row in rows]}
        if description.startswith("Save the read-back"):
            self.work_copy.write_bytes(self.work_copy.read_bytes() + b" saved")
            return {"filename": str(self.work_copy), "dbmod": 0}
        if description.startswith("ATGT sign annotation"):
            run_id = description.rsplit(" ", 1)[-1]
            self.readback = [
                {"handle": str(index), "action_id": "sign-001", "kind": kind,
                 "code": "P.102", "type": type_name, "layer": layer,
                 "station_text": station, "position": position, "rotation": rotation,
                 "vertices": vertices, "block_name": block_name, "scale": scale,
                 "asset_id": "sign:P.102:v1", "asset_sha256": self.imported_assets[0]["source_sha256"]}
                for index, (kind, type_name, layer, station, position, rotation, vertices, block_name, scale) in enumerate([
                    ("station_text", "DBText", "BIEN-BAO", "Km7+409", [95.0, 202.0, 0.0], 0.5, [], None, 0.0),
                    ("leader", "Leader", "BIEN-BAO", None, [], 0.0,
                     [[95.0, 202.0, 0.0], [98.0, 201.0, 0.0], [100.0, 200.0, 0.0]], None, 0.0),
                    ("sign_block", "BlockReference", "BIEN BAO", None, [100.0, 200.0, 0.0],
                     0.5, [], "ATGT_SIGN_P_102_V1", 1.0)], 1)]
            return {"run_id": run_id, "created": 3, "handles": ["1", "2", "3"]}
        if description.startswith("ATGT marking batch"):
            run_id = description.rsplit(" ", 1)[-1]
            self.readback = [{"handle": "4", "action_id": "mark-001", "kind": "marking_path_0",
                "code": "3.1a", "type": "Polyline", "layer": "ATGT", "linetype": "Continuous",
                "width": 0.2, "closed": False, "vertices": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]],
                "station_text": None, "position": [], "rotation": 0.0, "block_name": None, "scale": 0.0}]
            return {"run_id": run_id, "created": 1, "handles": ["4"]}
        if description.startswith("ATGT marking block batch"):
            run_id = description.rsplit(" ", 1)[-1]
            marking = next(row for row in self.imported_assets if row["asset_id"] == "marking:7.6:3m:v1")
            self.readback = [{"handle": "5", "action_id": "mark-block-001", "kind": "marking_block",
                "code": "7.6", "type": "BlockReference", "layer": "ATGT",
                "station_text": None, "position": [50.0, 2.0, 0.0], "rotation": 1.0,
                "vertices": [], "block_name": "VS_7.6_HINH_THOI_3M", "scale": 1.0,
                "asset_id": "marking:7.6:3m:v1", "asset_sha256": marking["source_sha256"],
                "width": 0.0, "closed": False, "linetype": "ByLayer"}]
            return {"run_id": run_id, "created": 1, "handles": ["5"]}
        raise AssertionError(description)


def test_work_copy_annotation_and_readback_are_one_guarded_contract(tmp_path):
    source = tmp_path / "BD TK ATGT TAY VAN CANH.dwg"
    source.write_bytes(b"source stays unchanged")
    output = tmp_path / "outputs"
    work_copy = output / "case-001" / "BD TK ATGT TAY VAN CANH__ATGT_case-001.dwg"
    rpc = FakeRpc(source, work_copy)
    service = configured_service(tmp_path, source, output, rpc)

    async def run():
        before = source.read_bytes()
        status = await service.status()
        assert status["source_matches"] and status["active"]["insunits"] == "Meters"
        session = await service.prepare_work_copy("case-001")
        assert session["captures_unsaved_in_memory_state"] is True
        assert source.read_bytes() == before and Path(session["work_copy"]) == work_copy
        await service.activate_work_copy("case-001")
        await service.sync_work_copy_units("case-001")
        imported = await service.import_marking_linetype("case-001")
        assert imported["verified"] and imported["pattern_m"] == [0.6, -0.6]
        assets = await service.import_assets(
            "case-001", "asset-import-001", ["sign:P.102:v1", "marking:7.6:3m:v1"])
        assert assets["verified"] is True and len(assets["assets"]) == 2
        reconciled = await service.import_assets(
            "case-001", "asset-import-001", ["sign:P.102:v1", "marking:7.6:3m:v1"])
        assert reconciled["import_id"] == "asset-import-001"
        assert len([d for d in rpc.execute_descriptions if d.startswith("ATGT guarded asset import")]) == 1
        result = await service.apply_annotation_batch("case-001", "run-001", [{
            "action_id": "sign-001", "sign_code": "P.102", "asset_id": "sign:P.102:v1",
            "station_text": "Km7+409", "x": 100.0, "y": 200.0,
            "z": 0.0, "rotation": 0.5, "scale_multiplier": 1.0, "block_layer": "BIEN BAO"}])
        assert result["verification"]["verified"] is True
        assert result["verification"]["action_kinds"]["sign-001"] == ["leader", "sign_block", "station_text"]
        marking = await service.apply_marking_batch("case-001", "mark-run-001", [{
            "action_id": "mark-001", "proposal_id": "edge:fixture", "marking_code": "3.1a",
            "layer": "ATGT", "linetype": "Continuous", "width_m": 0.2,
            "native_curve_geometry_verified": True, "geometry_evidence": "fixture native curve",
            "paths": [{"closed": False, "vertices": [
                {"x": 0.0, "y": 0.0, "bulge": 0.0}, {"x": 10.0, "y": 0.0, "bulge": 0.0}]}]}])
        assert marking["verification"]["verified"] is True
        marking_block = await service.apply_marking_block_batch(
            "case-001", "mark-block-run-001", [{
                "action_id": "mark-block-001", "proposal_id": "marking:fixture",
                "marking_code": "7.6", "asset_id": "marking:7.6:3m:v1",
                "x": 50.0, "y": 2.0, "z": 0.0, "alignment_tangent_rad": 1.0,
                "scale_multiplier": 1.0, "layer": "ATGT",
                "geometry_evidence": "fixture tangent and insertion point"}])
        assert marking_block["verification"]["verified"] is True
        manifest = json.loads((output / "case-001" / "session.json").read_text(encoding="utf-8"))
        assert [run["run_id"] for run in manifest["runs"]] == [
            "run-001", "mark-run-001", "mark-block-run-001"]
        assert manifest["asset_imports"][0]["assets"][0]["asset_id"] == "sign:P.102:v1"
        saved = await service.save_verified_work_copy("case-001")
        assert saved["verified_runs"] == ["run-001", "mark-run-001", "mark-block-run-001"] and saved["saved_sha256"]
        with pytest.raises(ValueError, match="already exists"):
            await service.apply_annotation_batch("case-001", "run-001", [{
                "action_id": "sign-001", "sign_code": "P.102", "asset_id": "sign:P.102:v1",
                "station_text": "Km7+409", "x": 100.0, "y": 200.0}])
        assert len([d for d in rpc.execute_descriptions if d.startswith("ATGT sign annotation")]) == 1
    asyncio.run(run())


def test_prepare_refuses_wrong_active_drawing_before_any_write(tmp_path):
    source = tmp_path / "expected.dwg"
    source.write_bytes(b"expected")
    other = tmp_path / "other.dwg"
    other.write_bytes(b"other")
    output = tmp_path / "outputs"
    rpc = FakeRpc(other, output / "case-002" / "expected__ATGT_case-002.dwg")
    service = CadSessionService(CadConfig(source, output), rpc)

    async def run():
        with pytest.raises(ValueError, match="not the configured source"):
            await service.prepare_work_copy("case-002")
        assert rpc.execute_descriptions == []
    asyncio.run(run())


def test_semantic_inventory_stays_bounded_and_geometry_is_exact_by_handle(tmp_path):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"source")
    rpc = FakeRpc(source, tmp_path / "unused.dwg")
    service = CadSessionService(CadConfig(source, tmp_path / "outputs"), rpc)

    async def run():
        survey = await service.inventory_semantics(2)
        assert survey["returned_groups"] == 2 and survey["total_groups"] == 3
        assert survey["role_hints_are_decisions"] is False
        assert survey["groups"][0]["semantic_status"] == "unverified"
        assert "centerline_candidate" in survey["groups"][0]["role_hints"]
        assert "road_edge_candidate" in survey["groups"][1]["role_hints"]
        assert survey["survey_id"].startswith("survey-")

        geometry = await service.extract_native_geometry(["a1", "B1"])
        assert geometry["requested_handles"] == ["A1", "B1"]
        assert [row["handle"] for row in geometry["entities"]] == ["A1", "B1"]
        assert all(row["exact_marking_geometry"] for row in geometry["entities"])
        assert geometry["geometry_set_id"].startswith("geometry-")

        with pytest.raises(ValueError, match="Duplicate"):
            await service.extract_native_geometry(["a1", "A1"])
        with pytest.raises(ValueError, match="hexadecimal"):
            await service.extract_native_geometry(["not-a-handle"])
        with pytest.raises(ValueError, match="max_groups"):
            await service.inventory_semantics(0)
    asyncio.run(run())


def test_user_declared_layers_bind_roles_to_exact_snapshot_without_name_guessing(tmp_path):
    """Owner contract: explicit roles select DO even though the heuristic does not recognize it."""
    source = tmp_path / "source.dwg"
    source.write_bytes(b"source")
    rpc = FakeRpc(source, tmp_path / "unused.dwg")
    service = CadSessionService(CadConfig(source, tmp_path / "outputs"), rpc)

    async def run():
        snapshot = (await service.inspect_active())["snapshot_id"]
        result = await service.survey_declared_layers(
            snapshot, ["DO"], ["mepduong"], limit=100, offset=0)
        assert result["role_source"] == "user_declared_exact_layer_names"
        assert result["role_counts"] == {"centerline": 1, "road_edge": 2}
        assert result["supported_role_counts"] == {"centerline": 1, "road_edge": 2}
        assert result["ready_for_geometry_extraction"] is True
        assert result["topology_status"] == "unverified"
        assert [row["handle"] for row in result["entities"]] == ["C1", "E1", "E2"]
        assert result["next_offset"] is None
        assert result["declaration_id"].startswith("layers-")

        with pytest.raises(ValueError, match="snapshot differs"):
            await service.survey_declared_layers("live-00000000000000000000", ["DO"], ["mepduong"])
        with pytest.raises(ValueError, match="both centerline and road_edge"):
            await service.survey_declared_layers(snapshot, ["DO"], ["do"])
    asyncio.run(run())


def test_work_copy_unit_drift_is_blocked_then_repaired_and_read_back(tmp_path):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"source")
    output = tmp_path / "outputs"
    work_copy = output / "case-004" / "source__ATGT_case-004.dwg"
    rpc = FakeRpc(source, work_copy)
    service = configured_service(tmp_path, source, output, rpc)

    async def run():
        await service.prepare_work_copy("case-004")
        rpc.work_copy_units = "Feet"
        await service.activate_work_copy("case-004")
        with pytest.raises(ValueError, match="INSUNITS differs"):
            await service.import_assets("case-004", "import-004", ["sign:P.102:v1"])
        assert not any(d.startswith("ATGT guarded asset import") for d in rpc.execute_descriptions)
        fixed = await service.sync_work_copy_units("case-004")
        assert fixed["verified"] and fixed["active"]["insunits"] == "Meters"
    asyncio.run(run())


@pytest.mark.parametrize("actions, message", [([], "1..50"), ([{
    "action_id": "bad", "sign_code": "102", "asset_id": "sign:P.102:v1",
    "station_text": "Km0+000", "x": 0.0, "y": 0.0}], "full sign code")])
def test_annotation_batch_rejects_unowned_or_ambiguous_input(tmp_path, actions, message):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"source")
    output = tmp_path / "outputs"
    work_copy = output / "case-003" / "source__ATGT_case-003.dwg"
    rpc = FakeRpc(source, work_copy)
    service = configured_service(tmp_path, source, output, rpc)
    async def run():
        await service.prepare_work_copy("case-003")
        await service.activate_work_copy("case-003")
        await service.sync_work_copy_units("case-003")
        await service.import_assets("case-003", "import-003", ["sign:P.102:v1"])
        with pytest.raises(ValueError, match=message):
            await service.apply_annotation_batch("case-003", "run-003", actions)
    asyncio.run(run())
