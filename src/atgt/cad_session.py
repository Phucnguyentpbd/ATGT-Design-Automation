"""Guarded work-copy and annotation operations for the ATGT Civil writer."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Any, Protocol
import math

from .asset_catalog import AssetCatalog


SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")
RUN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")
HANDLE_RE = re.compile(r"^[0-9A-Fa-f]{1,16}$")
SNAPSHOT_RE = re.compile(r"^live-[0-9a-f]{20}$")
SIGN_CODE_RE = re.compile(r"^(?:P|W|R|I|DP|S|IE|RE)\.[0-9]+[A-Za-z]?$", re.I)
REGAPP = "ATGT_AGENT"


class Rpc(Protocol):
    async def health(self) -> dict[str, Any]: ...
    async def query(self, code: str) -> Any: ...
    async def execute(self, code: str, description: str) -> Any: ...


@dataclass(frozen=True)
class CadConfig:
    expected_source: Path
    output_root: Path
    marking_template: Path | None = None
    sign_library: Path | None = None
    asset_catalog: Path | None = None
    annotation_text_handle: str = "38C635"
    annotation_leader_handle: str = "38BF28"
    annotation_block_handle: str = "38BF29"


def _same_path(left: str | Path, right: str | Path) -> bool:
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(os.path.abspath(str(right)))


def _literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _number(value: float) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("CAD coordinate must be numeric")
    if not float(value) == float(value) or abs(float(value)) == float("inf"):
        raise ValueError("CAD coordinate must be finite")
    return format(float(value), ".17g")


def _digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                            suffix=".json", delete=False) as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        staged = Path(stream.name)
    staged.replace(path)


class CadSessionService:
    def __init__(self, config: CadConfig, rpc: Rpc):
        marking_template = config.marking_template.resolve(strict=True) if config.marking_template else None
        sign_library = config.sign_library.resolve(strict=True) if config.sign_library else None
        asset_catalog_path = config.asset_catalog.resolve(strict=True) if config.asset_catalog else None
        if asset_catalog_path is not None and (sign_library is None or marking_template is None):
            raise ValueError("Asset catalog requires configured sign library and marking template")
        self.config = CadConfig(
            expected_source=config.expected_source.resolve(strict=True),
            output_root=config.output_root.resolve(),
            marking_template=marking_template,
            sign_library=sign_library,
            asset_catalog=asset_catalog_path,
            annotation_text_handle=config.annotation_text_handle,
            annotation_leader_handle=config.annotation_leader_handle,
            annotation_block_handle=config.annotation_block_handle)
        self.config.output_root.mkdir(parents=True, exist_ok=True)
        self.rpc = rpc
        self.asset_catalog = (AssetCatalog(asset_catalog_path, sign_library, marking_template)
                              if asset_catalog_path and sign_library and marking_template else None)

    async def import_marking_linetype(self, session_id: str) -> dict[str, Any]:
        if self.config.marking_template is None:
            raise ValueError("No marking template was configured at server startup")
        _, manifest = self._manifest(session_id)
        active = await self.inspect_active()
        self._validate_active_work_copy(manifest, active)
        template = str(self.config.marking_template)
        code = f"""
var sourcePath={_literal(template)}; var wanted=\"VACH_3.1B_0.6M\";
var targetTable=(Autodesk.AutoCAD.DatabaseServices.LinetypeTable)Transaction.GetObject(
    Database.LinetypeTableId, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var existed=targetTable.Has(wanted);
if(!existed) {{
    using(var side=new Autodesk.AutoCAD.DatabaseServices.Database(false,true)) {{
        side.ReadDwgFile(sourcePath, Autodesk.AutoCAD.DatabaseServices.FileOpenMode.OpenForReadAndAllShare, false, \"\");
        using(var sourceTr=side.TransactionManager.StartOpenCloseTransaction()) {{
            var sourceTable=(Autodesk.AutoCAD.DatabaseServices.LinetypeTable)sourceTr.GetObject(side.LinetypeTableId, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
            if(!sourceTable.Has(wanted)) throw new System.InvalidOperationException(\"Reviewed linetype is missing from configured template\");
            var ids=new Autodesk.AutoCAD.DatabaseServices.ObjectIdCollection(); ids.Add(sourceTable[wanted]);
            var mapping=new Autodesk.AutoCAD.DatabaseServices.IdMapping();
            side.WblockCloneObjects(ids, Database.LinetypeTableId, mapping, Autodesk.AutoCAD.DatabaseServices.DuplicateRecordCloning.Ignore, false);
        }}
    }}
}}
var verify=(Autodesk.AutoCAD.DatabaseServices.LinetypeTable)Transaction.GetObject(Database.LinetypeTableId, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
if(!verify.Has(wanted)) throw new System.InvalidOperationException(\"Linetype import did not create the target record\");
var record=(Autodesk.AutoCAD.DatabaseServices.LinetypeTableRecord)Transaction.GetObject(verify[wanted], Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var dashes=new System.Collections.Generic.List<double>(); for(int i=0;i<record.NumDashes;i++) dashes.Add(record.DashLengthAt(i));
return new{{name=wanted,existed,record.PatternLength,dashes,target_insunits=Database.Insunits.ToString()}};
"""
        result = await self.rpc.execute(code, "Import the reviewed 3.1b 0.6 m linetype into the isolated work copy")
        if not isinstance(result, dict) or result.get("name") != "VACH_3.1B_0.6M":
            raise ValueError("Civil did not return the expected marking linetype")
        dashes = [round(float(value), 9) for value in result.get("dashes", [])]
        if dashes != [0.6, -0.6] or result.get("target_insunits") != manifest.get("source_insunits"):
            raise ValueError("Imported 3.1b linetype pattern or target units are not the reviewed metric values")
        return {"session_id": session_id, "template": template, "linetype": result["name"],
                "pattern_m": dashes, "existed": result.get("existed") is True,
                "target_insunits": result["target_insunits"], "verified": True}

    def _session_dir(self, session_id: str) -> Path:
        if not SESSION_RE.fullmatch(session_id):
            raise ValueError("session_id must contain 3..64 letters, digits, _ or -")
        result = (self.config.output_root / session_id).resolve()
        if result.parent != self.config.output_root:
            raise ValueError("Session path escaped the configured output root")
        return result

    def _manifest(self, session_id: str) -> tuple[Path, dict[str, Any]]:
        path = self._session_dir(session_id) / "session.json"
        if not path.is_file():
            raise ValueError("Unknown CAD session; prepare the work copy first")
        return path, json.loads(path.read_text(encoding="utf-8"))

    async def inspect_active(self) -> dict[str, Any]:
        code = """
var dbmod = Convert.ToInt32(Autodesk.AutoCAD.ApplicationServices.Application.GetSystemVariable(\"DBMOD\"));
var min = Database.Extmin; var max = Database.Extmax;
var model = (Autodesk.AutoCAD.DatabaseServices.BlockTableRecord)Transaction.GetObject(
    Autodesk.AutoCAD.DatabaseServices.SymbolUtilityServices.GetBlockModelSpaceId(Database),
    Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
return new { document=Document.Name, filename=Database.Filename, dbmod,
    insunits=Database.Insunits.ToString(), measurement=Database.Measurement.ToString(),
    object_count=model.Cast<Autodesk.AutoCAD.DatabaseServices.ObjectId>().Count(),
    extmin=new[]{min.X,min.Y,min.Z}, extmax=new[]{max.X,max.Y,max.Z} };
"""
        result = await self.rpc.query(code)
        required = {"document", "filename", "dbmod", "insunits", "object_count", "extmin", "extmax"}
        if not isinstance(result, dict) or not required.issubset(result):
            raise ValueError("Civil inspection returned incomplete drawing identity")
        fingerprint = sha256(json.dumps(result, sort_keys=True, ensure_ascii=False,
                                           separators=(",", ":")).encode("utf-8")).hexdigest()
        return {**result, "snapshot_id": f"live-{fingerprint[:20]}"}

    async def status(self) -> dict[str, Any]:
        health = await self.rpc.health()
        active = await self.inspect_active()
        return {"connected": health.get("connected") is True,
                "endpoint_drawing": health.get("drawingName"), "active": active,
                "expected_source": str(self.config.expected_source),
                "source_matches": _same_path(active["filename"], self.config.expected_source),
                "write_policy": "distinct_work_copy_only", "batch_limit": 50,
                "asset_catalog": (self.asset_catalog.summary() if self.asset_catalog else {
                    "loaded": False, "reason": "Configure --asset-catalog and --sign-library"})}

    def list_assets(self, kind: str | None = None, code: str | None = None,
                    status: str | None = None, limit: int = 50,
                    offset: int = 0) -> dict[str, Any]:
        if self.asset_catalog is None:
            raise ValueError("No guarded asset catalog was configured at server startup")
        return {**self.asset_catalog.list(kind, code, status, limit, offset),
                "catalog": self.asset_catalog.summary(),
                "path_policy": "asset_id_only_no_caller_paths"}

    @staticmethod
    def _role_hints(layer: str) -> list[str]:
        """Return conservative discovery hints; these are never design decisions."""
        normalized = re.sub(r"[^A-Z0-9]+", " ", layer.upper()).strip()
        padded = f" {normalized} "
        compact = normalized.replace(" ", "")
        hints: list[str] = []
        token_sets = {
            "centerline_candidate": ((" TIM ", " CENTER ", " CENTERLINE ", " ALIGN ", " ALIGNMENT "),
                                         ("TIMTUYEN", "TIMDUONG", "CENTERLINE", "ALIGNMENT")),
            "road_edge_candidate": ((" MEP ", " EDGE ", " EOP ", " CURB ", " VIA ", " PHAN XE CHAY ", " PHAN VAI DUONG "),
                                    ("MEPDUONG", "BOVIA", "PHANXECHAY", "PHANVAIDUONG")),
            "branch_or_junction_candidate": ((" DAN SINH ", " NHANH ", " GIAO ", " ACCESS ", " SIDE ROAD ", " DUONG GOM "),
                                              ("DANSINH", "DUONGNHANH", "DUONGGOM", "SIDEROAD")),
            "existing_marking_candidate": ((" VACH ", " MARKING ", " SON "), ("VACH", "MARKING")),
            "sign_or_annotation_candidate": ((" BIEN BAO ", " SIGN ", " ATGT "), ("BIENBAO", "ATGT")),
        }
        for role, (word_tokens, compact_tokens) in token_sets.items():
            if any(token in padded for token in word_tokens) or any(token in compact for token in compact_tokens):
                hints.append(role)
        return hints

    async def inventory_semantics(self, max_groups: int = 80) -> dict[str, Any]:
        """Inventory bounded model-space layer/type groups without assigning road meaning."""
        if not isinstance(max_groups, int) or isinstance(max_groups, bool) or not 1 <= max_groups <= 200:
            raise ValueError("max_groups must be an integer in 1..200")
        before = await self.inspect_active()
        code = f"""
// ATGT_LAYER_INVENTORY_V1
var model=(Autodesk.AutoCAD.DatabaseServices.BlockTableRecord)Transaction.GetObject(
    Autodesk.AutoCAD.DatabaseServices.SymbolUtilityServices.GetBlockModelSpaceId(Database),
    Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var rows=new System.Collections.Generic.List<System.Collections.Generic.Dictionary<string,object>>();
foreach(Autodesk.AutoCAD.DatabaseServices.ObjectId id in model) {{
    var entity=Transaction.GetObject(id,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead) as Autodesk.AutoCAD.DatabaseServices.Entity;
    if(entity==null) continue;
    double[] lo=null; double[] hi=null;
    try {{ var ex=entity.GeometricExtents; lo=new[]{{ex.MinPoint.X,ex.MinPoint.Y,ex.MinPoint.Z}}; hi=new[]{{ex.MaxPoint.X,ex.MaxPoint.Y,ex.MaxPoint.Z}}; }} catch {{ }}
    var poly=entity as Autodesk.AutoCAD.DatabaseServices.Polyline;
    rows.Add(new System.Collections.Generic.Dictionary<string,object>{{
        {{"layer",entity.Layer}},{{"type",entity.GetRXClass().DxfName}},{{"linetype",entity.Linetype}},
        {{"color",entity.ColorIndex}},{{"handle",entity.Handle.ToString()}},{{"closed",poly!=null && poly.Closed}},
        {{"lo",lo}},{{"hi",hi}}
    }});
}}
var allGroups=rows.GroupBy(r=>System.Convert.ToString(r["layer"])+"\u001f"+System.Convert.ToString(r["type"])).ToList();
var groups=allGroups.OrderByDescending(g=>g.Count()).ThenBy(g=>System.Convert.ToString(g.First()["layer"]))
    .ThenBy(g=>System.Convert.ToString(g.First()["type"])).Take({max_groups}).Select(g=>{{
        var ext=g.Where(r=>r["lo"]!=null && r["hi"]!=null).ToList();
        return new {{
            layer=System.Convert.ToString(g.First()["layer"]), type=System.Convert.ToString(g.First()["type"]), count=g.Count(),
            linetypes=g.Select(r=>System.Convert.ToString(r["linetype"])).Distinct().OrderBy(x=>x).Take(10).ToList(),
            colors=g.Select(r=>System.Convert.ToInt32(r["color"])).Distinct().OrderBy(x=>x).Take(10).ToList(),
            closed_count=g.Count(r=>System.Convert.ToBoolean(r["closed"])),
            sample_handles=g.Take(5).Select(r=>System.Convert.ToString(r["handle"])).ToList(),
            extmin=ext.Count==0 ? null : new[]{{ext.Min(r=>((double[])r["lo"])[0]),ext.Min(r=>((double[])r["lo"])[1]),ext.Min(r=>((double[])r["lo"])[2])}},
            extmax=ext.Count==0 ? null : new[]{{ext.Max(r=>((double[])r["hi"])[0]),ext.Max(r=>((double[])r["hi"])[1]),ext.Max(r=>((double[])r["hi"])[2])}}
        }};
    }}).ToList();
return new {{filename=Database.Filename,dbmod=System.Convert.ToInt32(Autodesk.AutoCAD.ApplicationServices.Application.GetSystemVariable("DBMOD")),
    insunits=Database.Insunits.ToString(),total_entities=rows.Count,total_groups=allGroups.Count,returned_groups=groups.Count,groups}};
"""
        result = await self.rpc.query(code)
        required = {"filename", "dbmod", "insunits", "total_entities", "total_groups", "returned_groups", "groups"}
        if not isinstance(result, dict) or not required.issubset(result) or not isinstance(result["groups"], list):
            raise ValueError("Civil semantic inventory returned an unexpected result")
        if not _same_path(result["filename"], before["filename"]):
            raise ValueError("Active drawing changed during semantic inventory")
        if result["dbmod"] != before["dbmod"] or result["insunits"] != before["insunits"]:
            raise ValueError("Drawing state changed during semantic inventory")
        if len(result["groups"]) > max_groups or result["returned_groups"] != len(result["groups"]):
            raise ValueError("Civil semantic inventory exceeded its bounded result")
        groups = []
        for row in result["groups"]:
            if not isinstance(row, dict) or not {"layer", "type", "count", "sample_handles"}.issubset(row):
                raise ValueError("Civil semantic inventory contains an invalid group")
            groups.append({**row, "role_hints": self._role_hints(str(row["layer"])),
                           "semantic_status": "unverified"})
        payload = {**result, "groups": groups, "active_snapshot_id": before["snapshot_id"],
                   "role_hints_are_decisions": False,
                   "next_step": "review candidate layers, then extract exact native geometry by handle"}
        fingerprint = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                        separators=(",", ":")).encode("utf-8")).hexdigest()
        return {**payload, "survey_id": f"survey-{fingerprint[:20]}"}

    async def survey_declared_layers(self, snapshot_id: str,
                                     centerline_layers: list[str],
                                     road_edge_layers: list[str],
                                     limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Bind user-declared layer roles to one exact drawing snapshot.

        Layer membership is authoritative user input. Entity topology inside those layers remains
        unverified until the returned handles are inspected as native geometry.
        """
        if not isinstance(snapshot_id, str) or not SNAPSHOT_RE.fullmatch(snapshot_id):
            raise ValueError("snapshot_id must be the live snapshot returned by atgt_cad_status")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
            raise ValueError("limit must be an integer in 1..200")
        if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= 10000:
            raise ValueError("offset must be an integer in 0..10000")

        declarations: list[dict[str, str]] = []
        seen: dict[str, str] = {}
        for role, layers, maximum in (("centerline", centerline_layers, 20),
                                      ("road_edge", road_edge_layers, 40)):
            if not isinstance(layers, list) or not 1 <= len(layers) <= maximum:
                raise ValueError(f"{role}_layers must contain 1..{maximum} exact layer names")
            for layer in layers:
                if (not isinstance(layer, str) or not 1 <= len(layer) <= 255
                        or layer != layer.strip() or any(ord(char) < 32 for char in layer)):
                    raise ValueError("Layer names must be nonempty exact names without surrounding whitespace")
                key = layer.casefold()
                if key in seen:
                    if seen[key] == role:
                        raise ValueError(f"Duplicate layer declaration: {layer}")
                    raise ValueError(f"Layer cannot have both centerline and road_edge roles: {layer}")
                seen[key] = role
                declarations.append({"role": role, "layer": layer})

        before = await self.inspect_active()
        if before["snapshot_id"] != snapshot_id:
            raise ValueError("Active drawing snapshot differs from the user-declared layer context")
        csharp_items = ",".join(
            f"new {{role={_literal(item['role'])},layer={_literal(item['layer'])}}}"
            for item in declarations)
        code = f"""
// ATGT_DECLARED_LAYER_SURVEY_V1
var requested=new[]{{{csharp_items}}};
var layerTable=(Autodesk.AutoCAD.DatabaseServices.LayerTable)Transaction.GetObject(
    Database.LayerTableId,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var resolved=new System.Collections.Generic.Dictionary<string,string>(System.StringComparer.OrdinalIgnoreCase);
var actualNames=new System.Collections.Generic.Dictionary<string,string>(System.StringComparer.OrdinalIgnoreCase);
var missing=new System.Collections.Generic.List<string>();
foreach(var item in requested) {{
    if(!layerTable.Has(item.layer)) {{ missing.Add(item.layer); continue; }}
    var record=(Autodesk.AutoCAD.DatabaseServices.LayerTableRecord)Transaction.GetObject(
        layerTable[item.layer],Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
    resolved[record.Name]=item.role; actualNames[item.layer]=record.Name;
}}
var model=(Autodesk.AutoCAD.DatabaseServices.BlockTableRecord)Transaction.GetObject(
    Autodesk.AutoCAD.DatabaseServices.SymbolUtilityServices.GetBlockModelSpaceId(Database),
    Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var rows=new System.Collections.Generic.List<System.Collections.Generic.Dictionary<string,object>>();
foreach(Autodesk.AutoCAD.DatabaseServices.ObjectId id in model) {{
    var entity=Transaction.GetObject(id,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead) as Autodesk.AutoCAD.DatabaseServices.Entity;
    if(entity==null || !resolved.ContainsKey(entity.Layer)) continue;
    var poly=entity as Autodesk.AutoCAD.DatabaseServices.Polyline;
    var line=entity as Autodesk.AutoCAD.DatabaseServices.Line;
    var arc=entity as Autodesk.AutoCAD.DatabaseServices.Arc;
    var circle=entity as Autodesk.AutoCAD.DatabaseServices.Circle;
    var alignment=entity as Autodesk.Civil.DatabaseServices.Alignment;
    var curve=entity as Autodesk.AutoCAD.DatabaseServices.Curve;
    var mode=poly!=null ? "exact_polyline" : line!=null ? "exact_line" : arc!=null ? "exact_arc" :
        circle!=null ? "exact_circle" : alignment!=null ? "alignment_station_range" :
        curve!=null ? "generic_curve_requires_native_conversion" : "unsupported_non_curve";
    double? length=null;
    try {{
        if(poly!=null) length=poly.Length; else if(line!=null) length=line.Length; else if(arc!=null) length=arc.Length;
        else if(alignment!=null) length=alignment.Length;
        else if(curve!=null) length=curve.GetDistanceAtParameter(curve.EndParam)-curve.GetDistanceAtParameter(curve.StartParam);
    }} catch {{ }}
    double[] lo=null; double[] hi=null;
    try {{ var ex=entity.GeometricExtents; lo=new[]{{ex.MinPoint.X,ex.MinPoint.Y,ex.MinPoint.Z}}; hi=new[]{{ex.MaxPoint.X,ex.MaxPoint.Y,ex.MaxPoint.Z}}; }} catch {{ }}
    rows.Add(new System.Collections.Generic.Dictionary<string,object>{{
        {{"role",resolved[entity.Layer]}},{{"layer",entity.Layer}},{{"handle",entity.Handle.ToString()}},
        {{"type",entity.GetRXClass().DxfName}},{{"geometry_mode",mode}},{{"length",length}},
        {{"vertex_count",poly==null ? 0 : poly.NumberOfVertices}},{{"closed",poly!=null && poly.Closed}},
        {{"linetype",entity.Linetype}},{{"color",entity.ColorIndex}},{{"extmin",lo}},{{"extmax",hi}}
    }});
}}
var ordered=rows.OrderBy(r=>System.Convert.ToString(r["role"])).ThenBy(r=>System.Convert.ToString(r["layer"]))
    .ThenBy(r=>System.Convert.ToString(r["handle"])).ToList();
var page=ordered.Skip({offset}).Take({limit}).ToList();
var layerCounts=rows.GroupBy(r=>System.Convert.ToString(r["layer"]),System.StringComparer.OrdinalIgnoreCase)
    .Select(g=>new {{layer=g.Key,role=System.Convert.ToString(g.First()["role"]),count=g.Count(),
        supported=g.Count(r=>!System.Convert.ToString(r["geometry_mode"]).StartsWith("unsupported"))}})
    .OrderBy(x=>x.role).ThenBy(x=>x.layer).ToList();
var empty=requested.Where(item=>!missing.Contains(item.layer,System.StringComparer.OrdinalIgnoreCase)
    && !rows.Any(r=>System.String.Equals(System.Convert.ToString(r["layer"]),actualNames[item.layer],System.StringComparison.OrdinalIgnoreCase)))
    .Select(item=>item.layer).ToList();
return new {{filename=Database.Filename,dbmod=System.Convert.ToInt32(Autodesk.AutoCAD.ApplicationServices.Application.GetSystemVariable("DBMOD")),
    insunits=Database.Insunits.ToString(),declared_layers=requested,missing_layers=missing,empty_layers=empty,
    total_entities=ordered.Count,offset={offset},limit={limit},entities=page,layer_counts=layerCounts}};
"""
        result = await self.rpc.query(code)
        required = {"filename", "dbmod", "insunits", "declared_layers", "missing_layers",
                    "empty_layers", "total_entities", "offset", "limit", "entities", "layer_counts"}
        if not isinstance(result, dict) or not required.issubset(result):
            raise ValueError("Civil declared-layer survey returned an unexpected result")
        if not _same_path(result["filename"], before["filename"]):
            raise ValueError("Active drawing changed during declared-layer survey")
        if result["dbmod"] != before["dbmod"] or result["insunits"] != before["insunits"]:
            raise ValueError("Drawing state changed during declared-layer survey")
        if not isinstance(result["entities"], list) or len(result["entities"]) > limit:
            raise ValueError("Civil declared-layer survey exceeded its bounded page")

        role_counts = {"centerline": 0, "road_edge": 0}
        supported_counts = {"centerline": 0, "road_edge": 0}
        for row in result["entities"]:
            if not isinstance(row, dict) or row.get("role") not in role_counts:
                raise ValueError("Civil declared-layer survey contains an invalid role row")
        for row in result["layer_counts"]:
            role = row.get("role")
            if role not in role_counts:
                raise ValueError("Civil declared-layer survey contains an invalid role count")
            role_counts[role] += int(row.get("count", 0))
            supported_counts[role] += int(row.get("supported", 0))
        next_offset = offset + len(result["entities"])
        if next_offset >= int(result["total_entities"]):
            next_offset = None
        ready = (not result["missing_layers"] and not result["empty_layers"]
                 and supported_counts["centerline"] > 0 and supported_counts["road_edge"] > 0)
        payload = {**result, "active_snapshot_id": before["snapshot_id"],
                   "role_source": "user_declared_exact_layer_names",
                   "topology_status": "unverified",
                   "role_counts": role_counts, "supported_role_counts": supported_counts,
                   "ready_for_geometry_extraction": ready, "next_offset": next_offset,
                   "next_step": "extract native geometry for selected handles, then verify left/right/main/branch topology"}
        fingerprint = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                        separators=(",", ":")).encode("utf-8")).hexdigest()
        return {**payload, "declaration_id": f"layers-{fingerprint[:20]}"}

    async def extract_native_geometry(self, handles: list[str]) -> dict[str, Any]:
        """Read exact native data for a bounded set of entity handles."""
        if not isinstance(handles, list) or not 1 <= len(handles) <= 50:
            raise ValueError("handles must contain 1..50 values")
        normalized: list[str] = []
        for handle in handles:
            if not isinstance(handle, str) or not HANDLE_RE.fullmatch(handle):
                raise ValueError("Each handle must be 1..16 hexadecimal characters")
            upper = handle.upper()
            if upper in normalized:
                raise ValueError("Duplicate handles are not allowed")
            normalized.append(upper)
        before = await self.inspect_active()
        values = ",".join(_literal(value) for value in normalized)
        code = f"""
// ATGT_NATIVE_GEOMETRY_V1
var requested=new[]{{{values}}};
var rows=new System.Collections.Generic.List<System.Collections.Generic.Dictionary<string,object>>();
var totalPolylineVertices=0;
foreach(var textHandle in requested) {{
    Autodesk.AutoCAD.DatabaseServices.ObjectId id;
    try {{ id=Database.GetObjectId(false,new Autodesk.AutoCAD.DatabaseServices.Handle(System.Convert.ToInt64(textHandle,16)),0); }}
    catch {{ throw new System.InvalidOperationException("Unknown entity handle: "+textHandle); }}
    var entity=Transaction.GetObject(id,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead) as Autodesk.AutoCAD.DatabaseServices.Entity;
    if(entity==null || entity.IsErased) throw new System.InvalidOperationException("Handle is not a live entity: "+textHandle);
    var row=new System.Collections.Generic.Dictionary<string,object>();
    row["handle"]=entity.Handle.ToString(); row["type"]=entity.GetRXClass().DxfName; row["layer"]=entity.Layer;
    row["linetype"]=entity.Linetype; row["color"]=entity.ColorIndex; row["exact_marking_geometry"]=false;
    try {{ var ex=entity.GeometricExtents; row["extmin"]=new[]{{ex.MinPoint.X,ex.MinPoint.Y,ex.MinPoint.Z}}; row["extmax"]=new[]{{ex.MaxPoint.X,ex.MaxPoint.Y,ex.MaxPoint.Z}}; }} catch {{ row["extmin"]=null; row["extmax"]=null; }}
    var poly=entity as Autodesk.AutoCAD.DatabaseServices.Polyline;
    var line=entity as Autodesk.AutoCAD.DatabaseServices.Line;
    var arc=entity as Autodesk.AutoCAD.DatabaseServices.Arc;
    var circle=entity as Autodesk.AutoCAD.DatabaseServices.Circle;
    var alignment=entity as Autodesk.Civil.DatabaseServices.Alignment;
    var curve=entity as Autodesk.AutoCAD.DatabaseServices.Curve;
    if(poly!=null) {{
        if(poly.NumberOfVertices>20000 || totalPolylineVertices+poly.NumberOfVertices>50000)
            throw new System.InvalidOperationException("Native geometry exceeds the 20000-per-entity or 50000-total vertex safety limit");
        totalPolylineVertices+=poly.NumberOfVertices;
        var vertices=new System.Collections.Generic.List<double[]>();
        for(int i=0;i<poly.NumberOfVertices;i++) {{ var p=poly.GetPoint2dAt(i); vertices.Add(new[]{{p.X,p.Y,poly.GetBulgeAt(i),poly.GetStartWidthAt(i),poly.GetEndWidthAt(i)}}); }}
        row["representation"]="polyline_vertices_bulges_widths"; row["vertices"]=vertices; row["closed"]=poly.Closed;
        row["elevation"]=poly.Elevation; row["constant_width"]=poly.ConstantWidth; row["length"]=poly.Length; row["exact_marking_geometry"]=true;
    }} else if(line!=null) {{
        row["representation"]="line_endpoints"; row["start"]=new[]{{line.StartPoint.X,line.StartPoint.Y,line.StartPoint.Z}};
        row["end"]=new[]{{line.EndPoint.X,line.EndPoint.Y,line.EndPoint.Z}}; row["length"]=line.Length; row["exact_marking_geometry"]=true;
    }} else if(arc!=null) {{
        row["representation"]="arc_center_radius_angles"; row["center"]=new[]{{arc.Center.X,arc.Center.Y,arc.Center.Z}};
        row["radius"]=arc.Radius; row["start_angle"]=arc.StartAngle; row["end_angle"]=arc.EndAngle;
        row["normal"]=new[]{{arc.Normal.X,arc.Normal.Y,arc.Normal.Z}}; row["length"]=arc.Length; row["exact_marking_geometry"]=true;
    }} else if(circle!=null) {{
        row["representation"]="circle_center_radius"; row["center"]=new[]{{circle.Center.X,circle.Center.Y,circle.Center.Z}};
        row["radius"]=circle.Radius; row["normal"]=new[]{{circle.Normal.X,circle.Normal.Y,circle.Normal.Z}}; row["exact_marking_geometry"]=true;
    }} else if(alignment!=null) {{
        row["representation"]="civil_alignment_station_range"; row["name"]=alignment.Name;
        row["starting_station"]=alignment.StartingStation; row["ending_station"]=alignment.EndingStation; row["length"]=alignment.Length;
        row["exact_marking_geometry"]=false;
    }} else if(curve!=null) {{
        row["representation"]="generic_curve_endpoints"; row["start"]=new[]{{curve.StartPoint.X,curve.StartPoint.Y,curve.StartPoint.Z}};
        row["end"]=new[]{{curve.EndPoint.X,curve.EndPoint.Y,curve.EndPoint.Z}}; row["closed"]=curve.Closed;
        try {{ row["length"]=curve.GetDistanceAtParameter(curve.EndParam)-curve.GetDistanceAtParameter(curve.StartParam); }} catch {{ row["length"]=null; }}
    }} else {{ row["representation"]="non_curve_entity"; }}
    rows.Add(row);
}}
return new {{filename=Database.Filename,dbmod=System.Convert.ToInt32(Autodesk.AutoCAD.ApplicationServices.Application.GetSystemVariable("DBMOD")),
    insunits=Database.Insunits.ToString(),entities=rows}};
"""
        result = await self.rpc.query(code)
        if not isinstance(result, dict) or not isinstance(result.get("entities"), list):
            raise ValueError("Civil native geometry extraction returned an unexpected result")
        if not _same_path(result.get("filename", ""), before["filename"]):
            raise ValueError("Active drawing changed during native geometry extraction")
        if result.get("dbmod") != before["dbmod"] or result.get("insunits") != before["insunits"]:
            raise ValueError("Drawing state changed during native geometry extraction")
        actual = [str(row.get("handle", "")).upper() for row in result["entities"] if isinstance(row, dict)]
        if actual != normalized:
            raise ValueError("Civil native geometry extraction did not preserve the requested handle set and order")
        payload = {**result, "active_snapshot_id": before["snapshot_id"],
                   "requested_handles": normalized,
                   "geometry_policy": "exact native representation; generic curves require a later native offset/convert step"}
        fingerprint = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                        separators=(",", ":")).encode("utf-8")).hexdigest()
        return {**payload, "geometry_set_id": f"geometry-{fingerprint[:20]}"}

    async def prepare_work_copy(self, session_id: str) -> dict[str, Any]:
        session_dir = self._session_dir(session_id)
        manifest_path = session_dir / "session.json"
        if manifest_path.exists():
            raise ValueError("Session already exists; use a new session_id")
        active = await self.inspect_active()
        if not _same_path(active["filename"], self.config.expected_source):
            raise ValueError("Active drawing is not the configured source template")
        target = session_dir / f"{self.config.expected_source.stem}__ATGT_{session_id}.dwg"
        if target.exists():
            raise ValueError("Work-copy target already exists")
        session_dir.mkdir(parents=True, exist_ok=False)
        code = f"""
var target = {_literal(str(target))};
if (System.IO.File.Exists(target)) throw new System.InvalidOperationException(\"Work-copy target already exists\");
using (var clone = Database.Wblock()) {{
    clone.Insunits = Database.Insunits;
    clone.SaveAs(target, false, Database.OriginalFileVersion, Database.SecurityParameters);
}}
return new {{ source=Database.Filename, target, active_document=Document.Name }};
"""
        try:
            write_result = await self.rpc.execute(code, "Create an isolated ATGT work copy from the in-memory source drawing")
            after = await self.inspect_active()
            if not _same_path(after["filename"], self.config.expected_source):
                raise ValueError("Source drawing was no longer active after work-copy creation")
            if not target.is_file() or target.stat().st_size == 0:
                raise ValueError("Civil reported success but the work-copy file was not created")
            manifest = {
                "schema_version": 1, "session_id": session_id,
                "source": str(self.config.expected_source),
                "source_snapshot_id": active["snapshot_id"], "source_dbmod": active["dbmod"],
                "source_insunits": active["insunits"],
                "captures_unsaved_in_memory_state": active["dbmod"] != 0,
                "work_copy": str(target), "work_copy_sha256_at_creation": _digest(target),
                "work_copy_activated": False, "runs": [], "asset_imports": [],
                "asset_catalog_id": self.asset_catalog.catalog_id if self.asset_catalog else None,
                "asset_catalog_sha256": self.asset_catalog.sha256 if self.asset_catalog else None,
                "write_result": write_result,
            }
            _atomic_json(manifest_path, manifest)
            return manifest
        except Exception:
            # Preserve a created DWG for diagnosis; remove only an empty directory.
            if session_dir.exists() and not any(session_dir.iterdir()):
                session_dir.rmdir()
            raise

    async def activate_work_copy(self, session_id: str) -> dict[str, Any]:
        manifest_path, manifest = self._manifest(session_id)
        target = Path(manifest["work_copy"])
        if not target.is_file() or not _same_path(target.parent, manifest_path.parent):
            raise ValueError("Session work copy is missing or outside its session directory")
        code = f"""
var target = {_literal(str(target))};
var docs = Autodesk.AutoCAD.ApplicationServices.Application.DocumentManager;
Autodesk.AutoCAD.ApplicationServices.Document selected = null;
foreach (Autodesk.AutoCAD.ApplicationServices.Document d in docs) {{
    if (System.String.Equals(System.IO.Path.GetFullPath(d.Name), System.IO.Path.GetFullPath(target), System.StringComparison.OrdinalIgnoreCase)) {{ selected=d; break; }}
}}
if (selected == null) selected = docs.Open(target, false);
docs.MdiActiveDocument = selected;
return new {{ document=selected.Name, target }};
"""
        result = await self.rpc.execute(code, "Open and activate the isolated ATGT work copy")
        active = await self.inspect_active()
        if not _same_path(active["filename"], target):
            raise ValueError("Civil did not activate the expected work copy")
        manifest["work_copy_activated"] = True
        manifest["active_snapshot_id"] = active["snapshot_id"]
        _atomic_json(manifest_path, manifest)
        return {"session_id": session_id, "work_copy": str(target),
                "active": active, "activation_result": result}

    async def restore_source_active(self) -> dict[str, Any]:
        target = self.config.expected_source
        code = f"""
var target = {_literal(str(target))};
var docs = Autodesk.AutoCAD.ApplicationServices.Application.DocumentManager;
Autodesk.AutoCAD.ApplicationServices.Document selected = null;
foreach (Autodesk.AutoCAD.ApplicationServices.Document d in docs) {{
    if (System.String.Equals(System.IO.Path.GetFullPath(d.Name), System.IO.Path.GetFullPath(target), System.StringComparison.OrdinalIgnoreCase)) {{ selected=d; break; }}
}}
if (selected == null) throw new System.InvalidOperationException(\"Configured source drawing is not open\");
docs.MdiActiveDocument = selected;
return new {{ document=selected.Name, target }};
"""
        result = await self.rpc.execute(code, "Restore the configured source drawing as the active document")
        active = await self.inspect_active()
        if not _same_path(active["filename"], target):
            raise ValueError("Civil did not restore the configured source drawing")
        return {"source": str(target), "active": active, "activation_result": result}

    async def sync_work_copy_units(self, session_id: str) -> dict[str, Any]:
        manifest_path, manifest = self._manifest(session_id)
        active = await self.inspect_active()
        if not _same_path(active["filename"], manifest["work_copy"]):
            raise ValueError("Active drawing is not this session's work copy")
        expected = manifest.get("source_insunits")
        if not isinstance(expected, str) or not re.fullmatch(r"[A-Za-z]+", expected):
            raise ValueError("Session has no safe source INSUNITS value")
        if active["insunits"] != expected:
            code = f"""
var expected = {_literal(expected)};
var parsed = (Autodesk.AutoCAD.DatabaseServices.UnitsValue)System.Enum.Parse(
    typeof(Autodesk.AutoCAD.DatabaseServices.UnitsValue), expected, true);
Database.Insunits = parsed;
Database.SaveAs(Database.Filename, true, Database.OriginalFileVersion, Database.SecurityParameters);
return new {{ filename=Database.Filename, insunits=Database.Insunits.ToString() }};
"""
            await self.rpc.execute(code, "Normalize the isolated work copy INSUNITS to the source value")
            active = await self.inspect_active()
        if active["insunits"] != expected:
            raise ValueError("Work-copy INSUNITS still differs after normalization")
        manifest["work_copy_units_verified"] = True
        manifest["active_snapshot_id"] = active["snapshot_id"]
        _atomic_json(manifest_path, manifest)
        return {"session_id": session_id, "work_copy": manifest["work_copy"],
                "source_insunits": expected, "active": active, "verified": True}

    async def save_verified_work_copy(self, session_id: str) -> dict[str, Any]:
        manifest_path, manifest = self._manifest(session_id)
        if not manifest.get("runs"):
            raise ValueError("No read-back-verified CAD run is recorded for this session")
        active = await self.inspect_active()
        self._validate_active_work_copy(manifest, active)
        result = await self.rpc.execute("""
Database.SaveAs(Database.Filename, true, Database.OriginalFileVersion, Database.SecurityParameters);
return new { filename=Database.Filename, dbmod=Convert.ToInt32(
    Autodesk.AutoCAD.ApplicationServices.Application.GetSystemVariable("DBMOD")) };
""", "Save the read-back-verified isolated ATGT work copy")
        target = Path(manifest["work_copy"])
        if not target.is_file():
            raise ValueError("Work-copy file is missing after save")
        after = await self.inspect_active()
        self._validate_active_work_copy(manifest, after)
        manifest["saved_sha256"] = _digest(target)
        manifest["saved_snapshot_id"] = after["snapshot_id"]
        manifest["saved_after_verified_runs"] = [item["run_id"] for item in manifest["runs"]]
        _atomic_json(manifest_path, manifest)
        return {"session_id": session_id, "work_copy": str(target),
                "saved_sha256": manifest["saved_sha256"], "active": after,
                "save_result": result, "verified_runs": manifest["saved_after_verified_runs"]}

    def _validate_active_work_copy(self, manifest: dict[str, Any], active: dict[str, Any]) -> None:
        if not _same_path(active["filename"], manifest["work_copy"]):
            raise ValueError("Active drawing is not this session's work copy")
        if _same_path(active["filename"], self.config.expected_source):
            raise ValueError("Refusing to write to the configured source drawing")
        if active.get("insunits") != manifest.get("source_insunits"):
            raise ValueError("Work-copy INSUNITS differs from the source; CAD write is blocked")

    def _catalog_for_manifest(self, manifest: dict[str, Any]) -> AssetCatalog:
        if self.asset_catalog is None:
            raise ValueError("No guarded asset catalog was configured at server startup")
        self.asset_catalog.assert_unchanged()
        if (manifest.get("asset_catalog_id") != self.asset_catalog.catalog_id or
                manifest.get("asset_catalog_sha256") != self.asset_catalog.sha256):
            raise ValueError("CAD session was created with a different asset catalog version")
        return self.asset_catalog

    @staticmethod
    def _imported_assets(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for receipt in manifest.get("asset_imports", []):
            for asset in receipt.get("assets", []):
                previous = result.get(asset["asset_id"])
                if previous and previous.get("source_sha256") != asset.get("source_sha256"):
                    raise ValueError("Session contains conflicting versions of one asset_id")
                result[asset["asset_id"]] = asset
        return result

    async def import_assets(self, session_id: str, import_id: str,
                            asset_ids: list[str]) -> dict[str, Any]:
        """Import approved hash-locked block definitions into one verified work copy."""
        if not RUN_RE.fullmatch(import_id):
            raise ValueError("import_id must contain 3..64 letters, digits, _ or -")
        if not isinstance(asset_ids, list) or not 1 <= len(asset_ids) <= 50:
            raise ValueError("One asset import must contain 1..50 asset_ids")
        if any(not isinstance(value, str) for value in asset_ids) or len(set(asset_ids)) != len(asset_ids):
            raise ValueError("asset_ids must be unique strings")
        manifest_path, manifest = self._manifest(session_id)
        catalog = self._catalog_for_manifest(manifest)
        active = await self.inspect_active()
        self._validate_active_work_copy(manifest, active)
        if manifest.get("work_copy_units_verified") is not True:
            raise ValueError("Synchronize and verify work-copy units before importing assets")
        import_dir = manifest_path.parent / "imports"
        plan_path = import_dir / f"{import_id}-plan.json"
        receipt_path = import_dir / f"{import_id}-receipt.json"
        if plan_path.exists():
            verification = await self.verify_asset_import(session_id, import_id)
            if not verification["verified"]:
                raise ValueError("Staged asset import is incomplete; inspect the work copy and do not repeat the write")
            if receipt_path.is_file():
                return json.loads(receipt_path.read_text(encoding="utf-8"))
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            return self._finalize_asset_import(
                manifest_path, manifest, import_id, plan_path, plan["assets"],
                {"reconciled_after_existing_plan": True}, verification)

        previously_imported = self._imported_assets(manifest)
        planned: list[dict[str, Any]] = []
        for asset_id in asset_ids:
            record = catalog.get(asset_id, require_approved=True)
            source_path = catalog.source_path(record, require_approved=True)
            previous = previously_imported.get(asset_id)
            if previous and previous.get("source_sha256") != record.source_sha256:
                raise ValueError(f"Session already imported a different asset version: {asset_id}")
            planned.append({**record.public(), "source_path": str(source_path),
                            "allow_existing": previous is not None})
        _atomic_json(plan_path, {
            "schema_version": 1, "session_id": session_id, "import_id": import_id,
            "catalog_id": catalog.catalog_id, "catalog_sha256": catalog.sha256,
            "source_snapshot_id": active["snapshot_id"], "assets": planned})
        result = await self.rpc.execute(
            self._asset_import_code(import_id, planned), f"ATGT guarded asset import {import_id}")
        if not isinstance(result, dict) or not isinstance(result.get("assets"), list):
            raise ValueError("Civil asset import returned an unexpected result")
        if len(result["assets"]) != len(planned):
            raise ValueError("Civil asset import did not return every planned block definition")
        verification = await self.verify_asset_import(session_id, import_id)
        if not verification["verified"]:
            raise ValueError("Asset block definitions failed independent read-back")
        return self._finalize_asset_import(
            manifest_path, manifest, import_id, plan_path, planned, result, verification)

    def _finalize_asset_import(self, manifest_path: Path, manifest: dict[str, Any],
                               import_id: str, plan_path: Path,
                               planned: list[dict[str, Any]], write_result: dict[str, Any],
                               verification: dict[str, Any]) -> dict[str, Any]:
        receipt = {
            "schema_version": 1, "session_id": manifest["session_id"],
            "import_id": import_id, "kind": "asset_block_definitions",
            "plan": str(plan_path), "assets": [
                {key: item[key] for key in (
                    "asset_id", "kind", "code", "source_sha256", "target_block_name",
                    "placement_scale", "rotation_offset_rad")}
                for item in planned],
            "verified_snapshot_id": verification["snapshot_id"],
            "verified": True, "write_result": write_result,
            "verification": verification,
        }
        existing = [item for item in manifest.get("asset_imports", [])
                    if item.get("import_id") == import_id]
        if existing:
            return existing[0]
        manifest.setdefault("asset_imports", []).append({
            key: receipt[key] for key in (
                "import_id", "kind", "plan", "assets", "verified_snapshot_id", "verified")})
        _atomic_json(manifest_path, manifest)
        receipt_path = manifest_path.parent / "imports" / f"{import_id}-receipt.json"
        _atomic_json(receipt_path, receipt)
        return receipt

    def _asset_import_code(self, import_id: str, assets: list[dict[str, Any]]) -> str:
        rows = []
        for item in assets:
            source_block = ("null" if item["source_block_name"] is None
                            else _literal(item["source_block_name"]))
            rows.append("new { " + ", ".join([
                f"asset={_literal(item['asset_id'])}", f"code={_literal(item['code'])}",
                f"kind={_literal(item['kind'])}", f"hash={_literal(item['source_sha256'])}",
                f"path={_literal(item['source_path'])}", f"mode={_literal(item['import_mode'])}",
                f"sourceBlock=(string){source_block}",
                f"target={_literal(item['target_block_name'])}",
                f"allowExisting={'true' if item['allow_existing'] else 'false'}"]) + " }")
        return f"""
var importId={_literal(import_id)};
var regTable=(Autodesk.AutoCAD.DatabaseServices.RegAppTable)Transaction.GetObject(
    Database.RegAppTableId,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
if(!regTable.Has({_literal(REGAPP)})) {{ regTable.UpgradeOpen(); var rr=new Autodesk.AutoCAD.DatabaseServices.RegAppTableRecord();
    rr.Name={_literal(REGAPP)}; regTable.Add(rr); Transaction.AddNewlyCreatedDBObject(rr,true); }}
var items=new[]{{{','.join(rows)}}};
var results=new System.Collections.Generic.List<object>();
foreach(var item in items) {{
    var blockTable=(Autodesk.AutoCAD.DatabaseServices.BlockTable)Transaction.GetObject(
        Database.BlockTableId,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
    var existed=blockTable.Has(item.target);
    if(existed && !item.allowExisting)
        throw new System.InvalidOperationException("Target block name already exists without this session asset receipt: "+item.target);
    if(!existed) {{
        using(var side=new Autodesk.AutoCAD.DatabaseServices.Database(false,true)) {{
            side.ReadDwgFile(item.path,Autodesk.AutoCAD.DatabaseServices.FileOpenMode.OpenForReadAndAllShare,false,"");
            side.CloseInput(true);
            if(item.mode=="whole_dwg_as_block") {{
                Database.Insert(item.target,side,false);
            }} else if(item.mode=="named_block") {{
                using(var sourceTr=side.TransactionManager.StartOpenCloseTransaction()) {{
                    var sourceTable=(Autodesk.AutoCAD.DatabaseServices.BlockTable)sourceTr.GetObject(
                        side.BlockTableId,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
                    if(item.sourceBlock==null || !sourceTable.Has(item.sourceBlock))
                        throw new System.InvalidOperationException("Reviewed source block is missing: "+item.sourceBlock);
                    var ids=new Autodesk.AutoCAD.DatabaseServices.ObjectIdCollection(); ids.Add(sourceTable[item.sourceBlock]);
                    var map=new Autodesk.AutoCAD.DatabaseServices.IdMapping();
                    side.WblockCloneObjects(ids,Database.BlockTableId,map,
                        Autodesk.AutoCAD.DatabaseServices.DuplicateRecordCloning.Ignore,false);
                }}
            }} else throw new System.InvalidOperationException("Unsupported asset import mode");
        }}
        blockTable=(Autodesk.AutoCAD.DatabaseServices.BlockTable)Transaction.GetObject(
            Database.BlockTableId,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
        if(!blockTable.Has(item.target))
            throw new System.InvalidOperationException("Asset import did not create target block: "+item.target);
    }}
    var btr=(Autodesk.AutoCAD.DatabaseServices.BlockTableRecord)Transaction.GetObject(
        blockTable[item.target],Autodesk.AutoCAD.DatabaseServices.OpenMode.ForWrite);
    var existingData=btr.GetXDataForApplication({_literal(REGAPP)});
    if(existed && item.allowExisting) {{
        if(existingData==null) throw new System.InvalidOperationException("Existing target block lacks ATGT asset ownership: "+item.target);
        var old=existingData.AsArray();
        if(old.Length<7 || System.Convert.ToString(old[1].Value)!="ASSET_DEF" ||
           System.Convert.ToString(old[3].Value)!=item.asset || System.Convert.ToString(old[4].Value)!=item.hash)
            throw new System.InvalidOperationException("Existing target block has conflicting ATGT asset identity: "+item.target);
    }} else {{
        btr.XData=new Autodesk.AutoCAD.DatabaseServices.ResultBuffer(
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1001,{_literal(REGAPP)}),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,"ASSET_DEF"),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,importId),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.asset),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.hash),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.code),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.kind));
    }}
    results.Add(new{{asset_id=item.asset,code=item.code,kind=item.kind,source_sha256=item.hash,
        target_block_name=item.target,existed,entity_count=btr.Cast<Autodesk.AutoCAD.DatabaseServices.ObjectId>().Count()}});
}}
return new{{import_id=importId,assets=results}};
"""

    async def verify_asset_import(self, session_id: str, import_id: str) -> dict[str, Any]:
        if not RUN_RE.fullmatch(import_id):
            raise ValueError("Invalid import_id")
        manifest_path, manifest = self._manifest(session_id)
        active = await self.inspect_active()
        self._validate_active_work_copy(manifest, active)
        plan_path = manifest_path.parent / "imports" / f"{import_id}-plan.json"
        if not plan_path.is_file():
            raise ValueError("Unknown asset import plan")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assets = plan.get("assets", [])
        names = ",".join(_literal(item["target_block_name"]) for item in assets)
        code = f"""
// ATGT_ASSET_IMPORT_VERIFY_V1
var names=new[]{{{names}}};
var table=(Autodesk.AutoCAD.DatabaseServices.BlockTable)Transaction.GetObject(
    Database.BlockTableId,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var rows=new System.Collections.Generic.List<object>();
foreach(var name in names) {{
    if(!table.Has(name)) {{ rows.Add(new{{target_block_name=name,found=false,asset_id=(string)null,
        source_sha256=(string)null,code=(string)null,kind=(string)null,import_id=(string)null,entity_count=0}}); continue; }}
    var btr=(Autodesk.AutoCAD.DatabaseServices.BlockTableRecord)Transaction.GetObject(
        table[name],Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
    var data=btr.GetXDataForApplication({_literal(REGAPP)}); var values=data==null ? null : data.AsArray();
    rows.Add(new{{target_block_name=name,found=true,
        asset_id=values!=null && values.Length>=7 ? System.Convert.ToString(values[3].Value) : null,
        source_sha256=values!=null && values.Length>=7 ? System.Convert.ToString(values[4].Value) : null,
        code=values!=null && values.Length>=7 ? System.Convert.ToString(values[5].Value) : null,
        kind=values!=null && values.Length>=7 ? System.Convert.ToString(values[6].Value) : null,
        import_id=values!=null && values.Length>=7 ? System.Convert.ToString(values[2].Value) : null,
        entity_count=btr.Cast<Autodesk.AutoCAD.DatabaseServices.ObjectId>().Count()}});
}}
return rows;
"""
        rows = await self.rpc.query(code)
        if not isinstance(rows, list) or len(rows) != len(assets):
            raise ValueError("Civil asset-import read-back returned an unexpected result")
        issues: list[str] = []
        by_name = {row.get("target_block_name", "").casefold(): row for row in rows
                   if isinstance(row, dict)}
        for item in assets:
            row = by_name.get(item["target_block_name"].casefold())
            if not row or row.get("found") is not True:
                issues.append(f"{item['asset_id']}:missing_block")
                continue
            for field in ("asset_id", "source_sha256", "code", "kind"):
                if row.get(field) != item[field]:
                    issues.append(f"{item['asset_id']}:{field}")
            if int(row.get("entity_count", 0)) <= 0:
                issues.append(f"{item['asset_id']}:empty_block")
        return {"session_id": session_id, "import_id": import_id,
                "snapshot_id": active["snapshot_id"], "assets": rows,
                "verified": not issues and bool(rows), "issues": issues}

    async def apply_annotation_batch(self, session_id: str, run_id: str,
                                     actions: list[dict[str, Any]]) -> dict[str, Any]:
        if not RUN_RE.fullmatch(run_id):
            raise ValueError("run_id must contain 3..64 letters, digits, _ or -")
        if not 1 <= len(actions) <= 50:
            raise ValueError("One CAD annotation batch must contain 1..50 actions")
        manifest_path, manifest = self._manifest(session_id)
        self._catalog_for_manifest(manifest)
        imported_assets = self._imported_assets(manifest)
        action_ids: set[str] = set()
        normalized = []
        for item in actions:
            allowed = {"action_id", "sign_code", "asset_id", "station_text", "x", "y", "z",
                       "rotation", "scale_multiplier", "block_layer"}
            if set(item) - allowed:
                raise ValueError("Annotation action contains unknown fields")
            action_id = item.get("action_id", "")
            if not RUN_RE.fullmatch(action_id) or action_id in action_ids:
                raise ValueError("Annotation action ids must be unique safe identifiers")
            action_ids.add(action_id)
            sign_code = item.get("sign_code", "")
            if not SIGN_CODE_RE.fullmatch(sign_code):
                raise ValueError("Use a full sign code such as P.102")
            asset_id = item.get("asset_id", "")
            asset = imported_assets.get(asset_id) if isinstance(asset_id, str) else None
            if asset is None:
                raise ValueError("Sign asset_id must have a verified import receipt in this session")
            if asset.get("kind") != "sign" or asset.get("code", "").casefold() != sign_code.casefold():
                raise ValueError("Imported sign asset kind/code does not match the annotation")
            station_text = item.get("station_text", "")
            if not isinstance(station_text, str) or not re.fullmatch(r"(?i)km\d+\+\d+(?:[.,]\d+)?", station_text):
                raise ValueError("station_text must use the KmN+NNN format")
            multiplier = item.get("scale_multiplier", 1.0)
            if (not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool)
                    or not 0.01 <= float(multiplier) <= 100):
                raise ValueError("scale_multiplier must be in 0.01..100")
            rotation = item.get("rotation", 0.0)
            _number(rotation)
            final_scale = float(asset["placement_scale"]) * float(multiplier)
            if not 0.000001 <= final_scale <= 1000000:
                raise ValueError("Final sign scale is outside safe bounds")
            normalized.append({**item, "z": item.get("z", 0.0),
                               "rotation": float(rotation) + float(asset["rotation_offset_rad"]),
                               "scale_multiplier": float(multiplier), "scale": final_scale,
                               "block_name": asset["target_block_name"],
                               "asset_sha256": asset["source_sha256"],
                               "block_layer": item.get("block_layer", "BIEN BAO")})
        if any(r["run_id"] == run_id for r in manifest.get("runs", [])):
            raise ValueError("run_id already exists; do not repeat a CAD write")
        active = await self.inspect_active()
        self._validate_active_work_copy(manifest, active)
        plan_path = manifest_path.parent / "runs" / f"{run_id}-plan.json"
        if plan_path.exists():
            raise ValueError("run_id already has a staged plan; inspect read-back and use a new run_id")
        _atomic_json(plan_path, {"schema_version": 1, "session_id": session_id,
                                "run_id": run_id, "kind": "sign_annotation",
                                "source_snapshot_id": active["snapshot_id"], "actions": normalized})
        code = self._annotation_code(run_id, normalized)
        result = await self.rpc.execute(code, f"ATGT sign annotation batch {run_id}")
        if not isinstance(result, dict) or result.get("created") != len(normalized) * 3:
            raise ValueError("CAD annotation write did not return the expected entity count")
        verification = await self.verify_run(session_id, run_id, expected_actions=len(normalized))
        if not verification["verified"]:
            raise ValueError("CAD read-back did not verify the complete annotation batch")
        receipt = {"run_id": run_id, "kind": "sign_annotation", "plan": str(plan_path),
                   "created_entities": result["created"], "actions": len(normalized),
                   "verified_snapshot_id": verification["snapshot_id"]}
        manifest.setdefault("runs", []).append(receipt)
        _atomic_json(manifest_path, manifest)
        _atomic_json(manifest_path.parent / "runs" / f"{run_id}-receipt.json",
                     {**receipt, "write_result": result, "verification": verification})
        return {**receipt, "verification": verification}

    async def apply_marking_batch(self, session_id: str, run_id: str,
                                  actions: list[dict[str, Any]]) -> dict[str, Any]:
        if not RUN_RE.fullmatch(run_id):
            raise ValueError("run_id must contain 3..64 letters, digits, _ or -")
        if not 1 <= len(actions) <= 50:
            raise ValueError("One CAD marking batch must contain 1..50 actions")
        action_ids: set[str] = set()
        normalized: list[dict[str, Any]] = []
        total_paths = 0
        for item in actions:
            allowed = {"action_id", "proposal_id", "marking_code", "layer", "linetype",
                       "width_m", "native_curve_geometry_verified", "geometry_evidence", "paths"}
            if set(item) - allowed:
                raise ValueError("Marking action contains unknown fields")
            action_id = item.get("action_id", "")
            if not RUN_RE.fullmatch(action_id) or action_id in action_ids:
                raise ValueError("Marking action ids must be unique safe identifiers")
            action_ids.add(action_id)
            code = item.get("marking_code")
            if code not in {"3.1a", "3.1b", "4.4"}:
                raise ValueError("This writer supports only 3.1a, 3.1b and simple 4.4")
            if item.get("native_curve_geometry_verified") is not True:
                raise ValueError("Native curve geometry must be explicitly verified")
            for field in ("proposal_id", "layer", "linetype", "geometry_evidence"):
                if not isinstance(item.get(field), str) or not 1 <= len(item[field].strip()) <= 500:
                    raise ValueError(f"Missing or invalid {field}")
            width = item.get("width_m")
            if not isinstance(width, (int, float)) or isinstance(width, bool):
                raise ValueError("width_m must be numeric")
            if code in {"3.1a", "3.1b"} and not 0.15 <= float(width) <= 0.20:
                raise ValueError("3.1 marking width must be 0.15..0.20 m")
            if code == "4.4" and not 0.20 <= float(width) <= 0.40:
                raise ValueError("4.4 marking width must be 0.20..0.40 m")
            if code == "3.1a" and item["linetype"].casefold() != "continuous":
                raise ValueError("3.1a must use Continuous")
            if code == "3.1b" and "3.1b_0.6m" not in item["linetype"].casefold():
                raise ValueError("3.1b must use the reviewed 0.6 m / 0.6 m linetype")
            if code == "4.4" and item["linetype"].casefold() != "continuous":
                raise ValueError("Simple 4.4 must use Continuous")
            paths = item.get("paths")
            expected_paths = 3 if code == "4.4" else 1
            if not isinstance(paths, list) or len(paths) != expected_paths:
                raise ValueError(f"{code} requires exactly {expected_paths} path(s)")
            clean_paths = []
            for index, path in enumerate(paths):
                if not isinstance(path, dict) or set(path) != {"closed", "vertices"}:
                    raise ValueError("Each path needs only closed and vertices")
                closed = path["closed"]
                vertices = path["vertices"]
                if type(closed) is not bool or not isinstance(vertices, list) or not 2 <= len(vertices) <= 500:
                    raise ValueError("Invalid path closure or vertex count")
                if code == "4.4" and closed != (index == 0):
                    raise ValueError("4.4 path 0 is the closed outline; paths 1 and 2 are open diagonals")
                if code != "4.4" and closed:
                    raise ValueError("3.1 edge marking path must be open")
                clean_vertices = []
                for vertex in vertices:
                    if not isinstance(vertex, dict) or set(vertex) - {"x", "y", "bulge"} or not {"x", "y"}.issubset(vertex):
                        raise ValueError("Vertex needs x, y and optional bulge")
                    if any(not isinstance(vertex[key], (int, float)) or isinstance(vertex[key], bool)
                           for key in ("x", "y")) or ("bulge" in vertex and
                           (not isinstance(vertex["bulge"], (int, float)) or isinstance(vertex["bulge"], bool))):
                        raise ValueError("Vertex coordinates and bulge must be numeric")
                    point = {"x": float(vertex["x"]), "y": float(vertex["y"]),
                             "bulge": float(vertex.get("bulge", 0.0))}
                    for value in point.values():
                        _number(value)
                    clean_vertices.append(point)
                for left, right in zip(clean_vertices, clean_vertices[1:]):
                    if math.hypot(right["x"]-left["x"], right["y"]-left["y"]) <= 1e-6:
                        raise ValueError("Consecutive marking vertices must be distinct")
                clean_paths.append({"closed": closed, "vertices": clean_vertices})
            total_paths += len(clean_paths)
            normalized.append({**item, "width_m": float(width), "paths": clean_paths})
        if total_paths > 50:
            raise ValueError("One marking batch may create at most 50 polylines")
        manifest_path, manifest = self._manifest(session_id)
        if any(r["run_id"] == run_id for r in manifest.get("runs", [])):
            raise ValueError("run_id already exists; do not repeat a CAD write")
        active = await self.inspect_active()
        self._validate_active_work_copy(manifest, active)
        plan_path = manifest_path.parent / "runs" / f"{run_id}-plan.json"
        if plan_path.exists():
            raise ValueError("run_id already has a staged plan; inspect read-back and use a new run_id")
        _atomic_json(plan_path, {"schema_version": 1, "session_id": session_id,
                                "run_id": run_id, "kind": "marking_polyline",
                                "source_snapshot_id": active["snapshot_id"], "actions": normalized})
        result = await self.rpc.execute(self._marking_code(run_id, normalized),
                                        f"ATGT marking batch {run_id}")
        if not isinstance(result, dict) or result.get("created") != total_paths:
            raise ValueError("CAD marking write did not return the expected polyline count")
        verification = await self.verify_run(session_id, run_id, expected_actions=len(normalized))
        if not verification["verified"]:
            raise ValueError("CAD read-back did not verify the complete marking batch")
        receipt = {"run_id": run_id, "kind": "marking_polyline", "plan": str(plan_path),
                   "created_entities": total_paths, "actions": len(normalized),
                   "verified_snapshot_id": verification["snapshot_id"]}
        manifest.setdefault("runs", []).append(receipt)
        _atomic_json(manifest_path, manifest)
        _atomic_json(manifest_path.parent / "runs" / f"{run_id}-receipt.json",
                     {**receipt, "write_result": result, "verification": verification})
        return {**receipt, "verification": verification}

    async def apply_marking_block_batch(self, session_id: str, run_id: str,
                                        actions: list[dict[str, Any]]) -> dict[str, Any]:
        if not RUN_RE.fullmatch(run_id):
            raise ValueError("run_id must contain 3..64 letters, digits, _ or -")
        if not isinstance(actions, list) or not 1 <= len(actions) <= 50:
            raise ValueError("One marking-block batch must contain 1..50 actions")
        manifest_path, manifest = self._manifest(session_id)
        self._catalog_for_manifest(manifest)
        imported_assets = self._imported_assets(manifest)
        action_ids: set[str] = set()
        normalized: list[dict[str, Any]] = []
        for item in actions:
            allowed = {"action_id", "proposal_id", "marking_code", "asset_id", "x", "y", "z",
                       "alignment_tangent_rad", "scale_multiplier", "layer", "geometry_evidence"}
            if not isinstance(item, dict) or set(item) - allowed:
                raise ValueError("Marking-block action contains unknown fields")
            action_id = item.get("action_id", "")
            if not RUN_RE.fullmatch(action_id) or action_id in action_ids:
                raise ValueError("Marking-block action ids must be unique safe identifiers")
            action_ids.add(action_id)
            for field in ("proposal_id", "layer", "geometry_evidence"):
                if not isinstance(item.get(field), str) or not 1 <= len(item[field].strip()) <= 500:
                    raise ValueError(f"Missing or invalid {field}")
            asset_id = item.get("asset_id", "")
            asset = imported_assets.get(asset_id) if isinstance(asset_id, str) else None
            if asset is None:
                raise ValueError("Marking asset_id must have a verified import receipt in this session")
            if (asset.get("kind") != "marking_block" or
                    asset.get("code", "").casefold() != str(item.get("marking_code", "")).casefold()):
                raise ValueError("Imported marking asset kind/code does not match the action")
            for coordinate in ("x", "y", "z", "alignment_tangent_rad"):
                _number(item.get(coordinate, 0.0))
            multiplier = item.get("scale_multiplier", 1.0)
            if (not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool)
                    or not 0.01 <= float(multiplier) <= 100):
                raise ValueError("scale_multiplier must be in 0.01..100")
            final_scale = float(asset["placement_scale"]) * float(multiplier)
            if not 0.000001 <= final_scale <= 1000000:
                raise ValueError("Final marking-block scale is outside safe bounds")
            normalized.append({**item, "z": float(item.get("z", 0.0)),
                               "rotation": float(item.get("alignment_tangent_rad", 0.0)) +
                               float(asset["rotation_offset_rad"]),
                               "scale_multiplier": float(multiplier), "scale": final_scale,
                               "block_name": asset["target_block_name"],
                               "asset_sha256": asset["source_sha256"]})
        if any(r["run_id"] == run_id for r in manifest.get("runs", [])):
            raise ValueError("run_id already exists; do not repeat a CAD write")
        active = await self.inspect_active()
        self._validate_active_work_copy(manifest, active)
        plan_path = manifest_path.parent / "runs" / f"{run_id}-plan.json"
        if plan_path.exists():
            raise ValueError("run_id already has a staged plan; inspect read-back and use a new run_id")
        _atomic_json(plan_path, {"schema_version": 1, "session_id": session_id,
                                "run_id": run_id, "kind": "marking_block",
                                "source_snapshot_id": active["snapshot_id"], "actions": normalized})
        result = await self.rpc.execute(self._marking_block_code(run_id, normalized),
                                        f"ATGT marking block batch {run_id}")
        if not isinstance(result, dict) or result.get("created") != len(normalized):
            raise ValueError("CAD marking-block write did not return the expected entity count")
        verification = await self.verify_run(session_id, run_id, expected_actions=len(normalized))
        if not verification["verified"]:
            raise ValueError("CAD read-back did not verify the complete marking-block batch")
        receipt = {"run_id": run_id, "kind": "marking_block", "plan": str(plan_path),
                   "created_entities": len(normalized), "actions": len(normalized),
                   "verified_snapshot_id": verification["snapshot_id"]}
        manifest.setdefault("runs", []).append(receipt)
        _atomic_json(manifest_path, manifest)
        _atomic_json(manifest_path.parent / "runs" / f"{run_id}-receipt.json",
                     {**receipt, "write_result": result, "verification": verification})
        return {**receipt, "verification": verification}

    def _marking_block_code(self, run_id: str, actions: list[dict[str, Any]]) -> str:
        rows = []
        for item in actions:
            rows.append("new { " + ", ".join([
                f"action={_literal(item['action_id'])}", f"code={_literal(item['marking_code'])}",
                f"asset={_literal(item['asset_id'])}", f"assetHash={_literal(item['asset_sha256'])}",
                f"block={_literal(item['block_name'])}", f"layer={_literal(item['layer'])}",
                f"x={_number(item['x'])}", f"y={_number(item['y'])}", f"z={_number(item['z'])}",
                f"rotation={_number(item['rotation'])}", f"scale={_number(item['scale'])}"]) + " }")
        return f"""
var runId={_literal(run_id)};
var blockTable=(Autodesk.AutoCAD.DatabaseServices.BlockTable)Transaction.GetObject(
    Database.BlockTableId,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var layerTable=(Autodesk.AutoCAD.DatabaseServices.LayerTable)Transaction.GetObject(
    Database.LayerTableId,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var model=(Autodesk.AutoCAD.DatabaseServices.BlockTableRecord)Transaction.GetObject(
    Autodesk.AutoCAD.DatabaseServices.SymbolUtilityServices.GetBlockModelSpaceId(Database),
    Autodesk.AutoCAD.DatabaseServices.OpenMode.ForWrite);
var regTable=(Autodesk.AutoCAD.DatabaseServices.RegAppTable)Transaction.GetObject(
    Database.RegAppTableId,Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
if(!regTable.Has({_literal(REGAPP)})) {{ regTable.UpgradeOpen(); var rr=new Autodesk.AutoCAD.DatabaseServices.RegAppTableRecord();
    rr.Name={_literal(REGAPP)}; regTable.Add(rr); Transaction.AddNewlyCreatedDBObject(rr,true); }}
var items=new[]{{{','.join(rows)}}}; var handles=new System.Collections.Generic.List<string>();
foreach(var item in items) {{
    if(!blockTable.Has(item.block)) throw new System.InvalidOperationException("Missing imported marking block: "+item.block);
    if(!layerTable.Has(item.layer)) throw new System.InvalidOperationException("Missing marking block layer: "+item.layer);
    var position=new Autodesk.AutoCAD.Geometry.Point3d(item.x,item.y,item.z);
    var block=new Autodesk.AutoCAD.DatabaseServices.BlockReference(position,blockTable[item.block]);
    block.Rotation=item.rotation; block.ScaleFactors=new Autodesk.AutoCAD.Geometry.Scale3d(item.scale); block.Layer=item.layer;
    model.AppendEntity(block); Transaction.AddNewlyCreatedDBObject(block,true);
    block.XData=new Autodesk.AutoCAD.DatabaseServices.ResultBuffer(
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1001,{_literal(REGAPP)}),
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,runId),
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.action),
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,"marking_block"),
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.code),
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.asset),
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.assetHash));
    handles.Add(block.Handle.ToString());
}}
return new{{run_id=runId,created=handles.Count,handles}};
"""

    def _marking_code(self, run_id: str, actions: list[dict[str, Any]]) -> str:
        rows = []
        for item in actions:
            for index, path in enumerate(item["paths"]):
                points = ",".join(
                    "new[]{" + ",".join((_number(p["x"])+"D", _number(p["y"])+"D", _number(p["bulge"])+"D")) + "}"
                    for p in path["vertices"])
                rows.append("new { " + ", ".join([
                    f"action={_literal(item['action_id'])}", f"code={_literal(item['marking_code'])}",
                    f"kind={_literal(f'marking_path_{index}')}", f"layer={_literal(item['layer'])}",
                    f"linetype={_literal(item['linetype'])}", f"width={_number(item['width_m'])}D",
                    f"closed={'true' if path['closed'] else 'false'}", f"points=new[]{{{points}}}"]) + " }")
        return f"""
var runId={_literal(run_id)};
var model=(Autodesk.AutoCAD.DatabaseServices.BlockTableRecord)Transaction.GetObject(
    Autodesk.AutoCAD.DatabaseServices.SymbolUtilityServices.GetBlockModelSpaceId(Database), Autodesk.AutoCAD.DatabaseServices.OpenMode.ForWrite);
var layers=(Autodesk.AutoCAD.DatabaseServices.LayerTable)Transaction.GetObject(Database.LayerTableId, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var linetypes=(Autodesk.AutoCAD.DatabaseServices.LinetypeTable)Transaction.GetObject(Database.LinetypeTableId, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var regTable=(Autodesk.AutoCAD.DatabaseServices.RegAppTable)Transaction.GetObject(Database.RegAppTableId, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
if (!regTable.Has({_literal(REGAPP)})) {{ regTable.UpgradeOpen(); var record=new Autodesk.AutoCAD.DatabaseServices.RegAppTableRecord();
    record.Name={_literal(REGAPP)}; regTable.Add(record); Transaction.AddNewlyCreatedDBObject(record,true); }}
var items=new[]{{{','.join(rows)}}};
var handles=new System.Collections.Generic.List<string>();
foreach(var item in items) {{
    if(!layers.Has(item.layer)) throw new System.InvalidOperationException(\"Missing marking layer: \"+item.layer);
    if(!linetypes.Has(item.linetype)) throw new System.InvalidOperationException(\"Missing marking linetype: \"+item.linetype);
    var poly=new Autodesk.AutoCAD.DatabaseServices.Polyline(item.points.Length);
    for(int i=0;i<item.points.Length;i++) poly.AddVertexAt(i,new Autodesk.AutoCAD.Geometry.Point2d(item.points[i][0],item.points[i][1]),item.points[i][2],item.width,item.width);
    poly.Closed=item.closed; poly.Layer=item.layer; poly.Linetype=item.linetype; poly.ConstantWidth=item.width;
    model.AppendEntity(poly); Transaction.AddNewlyCreatedDBObject(poly,true);
    poly.XData=new Autodesk.AutoCAD.DatabaseServices.ResultBuffer(
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1001,{_literal(REGAPP)}),
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,runId),
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.action),
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.kind),
        new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.code));
    handles.Add(poly.Handle.ToString());
}}
return new{{run_id=runId,created=handles.Count,handles}};
"""

    def _annotation_code(self, run_id: str, actions: list[dict[str, Any]]) -> str:
        rows = []
        for item in actions:
            rows.append("new { " + ", ".join([
                f"action={_literal(item['action_id'])}", f"code={_literal(item['sign_code'])}",
                f"asset={_literal(item['asset_id'])}", f"assetHash={_literal(item['asset_sha256'])}",
                f"block={_literal(item['block_name'])}", f"station={_literal(item['station_text'])}",
                f"x={_number(item['x'])}", f"y={_number(item['y'])}", f"z={_number(item['z'])}",
                f"rotation={_number(item['rotation'])}", f"scale={_number(item['scale'])}",
                f"layer={_literal(item['block_layer'])}"]) + " }")
        return f"""
var runId = {_literal(run_id)};
var blockTable = (Autodesk.AutoCAD.DatabaseServices.BlockTable)Transaction.GetObject(Database.BlockTableId, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var model = (Autodesk.AutoCAD.DatabaseServices.BlockTableRecord)Transaction.GetObject(
    Autodesk.AutoCAD.DatabaseServices.SymbolUtilityServices.GetBlockModelSpaceId(Database), Autodesk.AutoCAD.DatabaseServices.OpenMode.ForWrite);
var texts = new System.Collections.Generic.List<Autodesk.AutoCAD.DatabaseServices.DBText>();
var leaders = new System.Collections.Generic.List<Autodesk.AutoCAD.DatabaseServices.Leader>();
var blocks = new System.Collections.Generic.List<Autodesk.AutoCAD.DatabaseServices.BlockReference>();
foreach (Autodesk.AutoCAD.DatabaseServices.ObjectId id in model) {{
    var obj = Transaction.GetObject(id, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
    var t = obj as Autodesk.AutoCAD.DatabaseServices.DBText;
    var l = obj as Autodesk.AutoCAD.DatabaseServices.Leader;
    var b = obj as Autodesk.AutoCAD.DatabaseServices.BlockReference;
    if (t != null && System.String.Equals(t.TextString, \"km7+409\", System.StringComparison.OrdinalIgnoreCase)
        && System.String.Equals(t.Layer, \"BIEN-BAO\", System.StringComparison.OrdinalIgnoreCase)
        && System.Math.Abs(t.Height-2.0) < 0.01) texts.Add(t);
    if (l != null && l.NumVertices == 3
        && System.String.Equals(l.Layer, \"BIEN-BAO\", System.StringComparison.OrdinalIgnoreCase)
        && System.String.Equals(l.DimensionStyleName, \"duonggiao\", System.StringComparison.OrdinalIgnoreCase)) leaders.Add(l);
    if (b != null) {{
        var rec=(Autodesk.AutoCAD.DatabaseServices.BlockTableRecord)Transaction.GetObject(b.DynamicBlockTableRecord, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
        if (System.String.Equals(rec.Name, \"207a_245a\", System.StringComparison.OrdinalIgnoreCase)) blocks.Add(b);
    }}
}}
Autodesk.AutoCAD.DatabaseServices.DBText sourceText = null;
Autodesk.AutoCAD.DatabaseServices.Leader sourceLeader = null;
Autodesk.AutoCAD.DatabaseServices.BlockReference sourceBlock = null;
var archetypeMatches = 0;
foreach (var t in texts) foreach (var l in leaders) {{
    if (t.Position.DistanceTo(l.VertexAt(0)) > 8.0) continue;
    foreach (var b in blocks) {{
        if (b.Position.DistanceTo(l.VertexAt(l.NumVertices-1)) > 0.10) continue;
        sourceText=t; sourceLeader=l; sourceBlock=b; archetypeMatches++;
    }}
}}
if (archetypeMatches != 1 || sourceText == null || sourceLeader == null || sourceBlock == null)
    throw new System.InvalidOperationException(\"Expected exactly one reviewed km7+409/207a_245a annotation archetype; found \" + archetypeMatches);
var regTable = (Autodesk.AutoCAD.DatabaseServices.RegAppTable)Transaction.GetObject(Database.RegAppTableId, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
if (!regTable.Has({_literal(REGAPP)})) {{
    regTable.UpgradeOpen(); var record = new Autodesk.AutoCAD.DatabaseServices.RegAppTableRecord(); record.Name={_literal(REGAPP)};
    regTable.Add(record); Transaction.AddNewlyCreatedDBObject(record,true);
}}
var items = new[] {{ {', '.join(rows)} }};
var created = new System.Collections.Generic.List<string>();
foreach (var item in items) {{
    if (!blockTable.Has(item.block)) throw new System.InvalidOperationException(\"Missing block definition: \" + item.block);
    if (!Database.LayerTableId.IsValid) throw new System.InvalidOperationException(\"Drawing layer table is unavailable\");
    var anchor = new Autodesk.AutoCAD.Geometry.Point3d(item.x,item.y,item.z);
    var rotate = Autodesk.AutoCAD.Geometry.Matrix3d.Rotation(item.rotation-sourceBlock.Rotation, Autodesk.AutoCAD.Geometry.Vector3d.ZAxis, sourceBlock.Position);
    var move = Autodesk.AutoCAD.Geometry.Matrix3d.Displacement(anchor-sourceBlock.Position);
    var text = (Autodesk.AutoCAD.DatabaseServices.DBText)sourceText.Clone(); text.TransformBy(rotate); text.TransformBy(move); text.TextString=item.station;
    var leader = (Autodesk.AutoCAD.DatabaseServices.Leader)sourceLeader.Clone(); leader.TransformBy(rotate); leader.TransformBy(move);
    var sign = new Autodesk.AutoCAD.DatabaseServices.BlockReference(anchor, blockTable[item.block]); sign.Rotation=item.rotation;
    sign.ScaleFactors = new Autodesk.AutoCAD.Geometry.Scale3d(item.scale); sign.Layer=item.layer;
    foreach (Autodesk.AutoCAD.DatabaseServices.Entity entity in new Autodesk.AutoCAD.DatabaseServices.Entity[] {{ text,leader,sign }}) {{
        model.AppendEntity(entity); Transaction.AddNewlyCreatedDBObject(entity,true);
        var kind = entity is Autodesk.AutoCAD.DatabaseServices.DBText ? \"station_text\" : entity is Autodesk.AutoCAD.DatabaseServices.Leader ? \"leader\" : \"sign_block\";
        entity.XData = new Autodesk.AutoCAD.DatabaseServices.ResultBuffer(
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1001,{_literal(REGAPP)}),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,runId),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.action),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,kind),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.code),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.asset),
            new Autodesk.AutoCAD.DatabaseServices.TypedValue(1000,item.assetHash));
        created.Add(entity.Handle.ToString());
    }}
}}
return new {{ run_id=runId, created=created.Count, handles=created }};
"""

    async def verify_run(self, session_id: str, run_id: str,
                         expected_actions: int | None = None) -> dict[str, Any]:
        if not RUN_RE.fullmatch(run_id):
            raise ValueError("Invalid run_id")
        manifest_path, manifest = self._manifest(session_id)
        active = await self.inspect_active()
        self._validate_active_work_copy(manifest, active)
        code = f"""
var model = (Autodesk.AutoCAD.DatabaseServices.BlockTableRecord)Transaction.GetObject(
    Autodesk.AutoCAD.DatabaseServices.SymbolUtilityServices.GetBlockModelSpaceId(Database), Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
var rows = new System.Collections.Generic.List<object>();
foreach (Autodesk.AutoCAD.DatabaseServices.ObjectId id in model) {{
    var entity = Transaction.GetObject(id, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead) as Autodesk.AutoCAD.DatabaseServices.Entity;
    if (entity == null) continue; var data=entity.GetXDataForApplication({_literal(REGAPP)}); if (data == null) continue;
    var values=data.AsArray(); if (values.Length < 5 || System.Convert.ToString(values[1].Value) != {_literal(run_id)}) continue;
    var action=System.Convert.ToString(values[2].Value); var kind=System.Convert.ToString(values[3].Value);
    var code=System.Convert.ToString(values[4].Value);
    var assetId=values.Length>=7 ? System.Convert.ToString(values[5].Value) : null;
    var assetHash=values.Length>=7 ? System.Convert.ToString(values[6].Value) : null;
    var text=entity as Autodesk.AutoCAD.DatabaseServices.DBText;
    var leader=entity as Autodesk.AutoCAD.DatabaseServices.Leader;
    var block=entity as Autodesk.AutoCAD.DatabaseServices.BlockReference;
    var poly=entity as Autodesk.AutoCAD.DatabaseServices.Polyline;
    if (text != null) rows.Add(new {{ handle=entity.Handle.ToString(), action_id=action, kind, code, asset_id=assetId, asset_sha256=assetHash,
        type=\"DBText\", layer=entity.Layer, station_text=text.TextString,
        position=new[]{{text.Position.X,text.Position.Y,text.Position.Z}}, rotation=text.Rotation,
        vertices=new System.Collections.Generic.List<double[]>(), block_name=(string)null, scale=0.0,
        width=0.0, closed=false, linetype=entity.Linetype }});
    else if (leader != null) {{
        var pts=new System.Collections.Generic.List<double[]>();
        for (int i=0;i<leader.NumVertices;i++) {{ var p=leader.VertexAt(i); pts.Add(new[]{{p.X,p.Y,p.Z}}); }}
        rows.Add(new {{ handle=entity.Handle.ToString(), action_id=action, kind, code, asset_id=assetId, asset_sha256=assetHash,
            type=\"Leader\", layer=entity.Layer, station_text=(string)null,
            position=new double[]{{}}, rotation=0.0, vertices=pts, block_name=(string)null, scale=0.0,
            width=0.0, closed=false, linetype=entity.Linetype }});
    }} else if (block != null) {{
        var rec=(Autodesk.AutoCAD.DatabaseServices.BlockTableRecord)Transaction.GetObject(block.DynamicBlockTableRecord, Autodesk.AutoCAD.DatabaseServices.OpenMode.ForRead);
        rows.Add(new {{ handle=entity.Handle.ToString(), action_id=action, kind, code, asset_id=assetId, asset_sha256=assetHash,
            type=\"BlockReference\", layer=entity.Layer, station_text=(string)null,
            position=new[]{{block.Position.X,block.Position.Y,block.Position.Z}}, rotation=block.Rotation,
            vertices=new System.Collections.Generic.List<double[]>(), block_name=rec.Name, scale=block.ScaleFactors.X,
            width=0.0, closed=false, linetype=entity.Linetype }});
    }} else if (poly != null) {{
        var pts=new System.Collections.Generic.List<double[]>();
        for(int i=0;i<poly.NumberOfVertices;i++) {{ var p=poly.GetPoint2dAt(i); pts.Add(new[]{{p.X,p.Y,poly.GetBulgeAt(i)}}); }}
        rows.Add(new {{ handle=entity.Handle.ToString(), action_id=action, kind, code, asset_id=assetId, asset_sha256=assetHash,
            type="Polyline", layer=entity.Layer, station_text=(string)null,
            position=new double[]{{}}, rotation=0.0, vertices=pts, block_name=(string)null, scale=0.0,
            width=poly.ConstantWidth, closed=poly.Closed, linetype=entity.Linetype }});
    }}
}}
return rows;
"""
        rows = await self.rpc.query(code)
        if not isinstance(rows, list):
            raise ValueError("CAD read-back returned an unexpected result")
        by_action: dict[str, dict[str, dict[str, Any]]] = {}
        duplicate_kinds: list[str] = []
        for row in rows:
            if row["kind"] in by_action.setdefault(row["action_id"], {}):
                duplicate_kinds.append(f"{row['action_id']}:{row['kind']}")
            by_action.setdefault(row["action_id"], {})[row["kind"]] = row
        count_ok = expected_actions is None or len(by_action) == expected_actions
        geometry_issues: list[str] = []
        geometry_issues.extend(f"duplicate_owned_entity:{item}" for item in duplicate_kinds)
        plan_path = manifest_path.parent / "runs" / f"{run_id}-plan.json"
        expected_by_id: dict[str, dict[str, Any]] = {}
        plan_kind = None
        if plan_path.is_file():
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan_kind = plan.get("kind")
            expected_by_id = {item["action_id"]: item for item in plan.get("actions", [])}
            if expected_actions is None:
                count_ok = len(by_action) == len(expected_by_id)
        if expected_by_id and set(by_action) != set(expected_by_id):
            geometry_issues.append("action_ids_do_not_match_staged_plan")
        if plan_kind in {"marking_polyline", "marking_block"}:
            complete = True
        else:
            complete = all(set(kinds) == {"station_text", "leader", "sign_block"}
                           for kinds in by_action.values())
        for action_id, expected in expected_by_id.items():
            group = by_action.get(action_id)
            if plan_kind == "marking_block":
                if not group or set(group) != {"marking_block"}:
                    complete = False
                    geometry_issues.append(f"{action_id}:marking_block_set")
                    continue
                block = group["marking_block"]
                if block.get("type") != "BlockReference" or block.get("code") != expected["marking_code"]:
                    geometry_issues.append(f"{action_id}:type_or_code")
                if block.get("block_name", "").casefold() != expected["block_name"].casefold():
                    geometry_issues.append(f"{action_id}:block_name")
                if block.get("layer", "").casefold() != expected["layer"].casefold():
                    geometry_issues.append(f"{action_id}:layer")
                if (block.get("asset_id") != expected["asset_id"] or
                        block.get("asset_sha256") != expected["asset_sha256"]):
                    geometry_issues.append(f"{action_id}:asset_identity")
                target = [float(expected[k]) for k in ("x", "y", "z")]
                if len(block.get("position", [])) != 3 or math.dist(block["position"], target) > 1e-4:
                    geometry_issues.append(f"{action_id}:position")
                angle_delta = abs((float(block.get("rotation", 0)) - float(expected["rotation"]) + math.pi) % (2*math.pi) - math.pi)
                if angle_delta > 1e-6 or abs(float(block.get("scale", 0))-float(expected["scale"])) > 1e-6:
                    geometry_issues.append(f"{action_id}:transform")
                continue
            if plan_kind == "marking_polyline":
                expected_kinds = {f"marking_path_{index}" for index in range(len(expected["paths"]))}
                if not group or set(group) != expected_kinds:
                    complete = False
                    geometry_issues.append(f"{action_id}:path_set")
                    continue
                for index, path in enumerate(expected["paths"]):
                    row = group[f"marking_path_{index}"]
                    if row.get("type") != "Polyline" or row.get("code") != expected["marking_code"]:
                        geometry_issues.append(f"{action_id}:path_{index}:type_or_code")
                    if row.get("layer", "").casefold() != expected["layer"].casefold():
                        geometry_issues.append(f"{action_id}:path_{index}:layer")
                    if row.get("linetype", "").casefold() != expected["linetype"].casefold():
                        geometry_issues.append(f"{action_id}:path_{index}:linetype")
                    if bool(row.get("closed")) != path["closed"] or abs(float(row.get("width", 0))-float(expected["width_m"])) > 1e-6:
                        geometry_issues.append(f"{action_id}:path_{index}:width_or_closure")
                    actual_vertices = row.get("vertices", [])
                    if len(actual_vertices) != len(path["vertices"]):
                        geometry_issues.append(f"{action_id}:path_{index}:vertex_count")
                    else:
                        for actual, wanted in zip(actual_vertices, path["vertices"]):
                            target = [float(wanted["x"]), float(wanted["y"]), float(wanted.get("bulge", 0))]
                            if len(actual) != 3 or math.dist(actual, target) > 1e-6:
                                geometry_issues.append(f"{action_id}:path_{index}:vertex_geometry")
                                break
                continue
            if not group or set(group) != {"station_text", "leader", "sign_block"}:
                continue
            text, leader, block = group["station_text"], group["leader"], group["sign_block"]
            if text.get("type") != "DBText" or leader.get("type") != "Leader" or block.get("type") != "BlockReference":
                geometry_issues.append(f"{action_id}:entity_type")
            if text.get("station_text") != expected["station_text"]:
                geometry_issues.append(f"{action_id}:station_text")
            if block.get("block_name", "").casefold() != expected["block_name"].casefold():
                geometry_issues.append(f"{action_id}:block_name")
            if (block.get("asset_id") != expected["asset_id"] or
                    block.get("asset_sha256") != expected["asset_sha256"]):
                geometry_issues.append(f"{action_id}:asset_identity")
            if text.get("layer", "").casefold() != "bien-bao" or leader.get("layer", "").casefold() != "bien-bao":
                geometry_issues.append(f"{action_id}:annotation_layer")
            if block.get("layer", "").casefold() != expected["block_layer"].casefold():
                geometry_issues.append(f"{action_id}:block_layer")
            target = [float(expected[k]) for k in ("x", "y", "z")]
            block_position = block.get("position", [])
            vertices = leader.get("vertices", [])
            if len(block_position) != 3 or math.dist(block_position, target) > 1e-4:
                geometry_issues.append(f"{action_id}:block_position")
            if len(vertices) != 3 or math.dist(vertices[-1], target) > 0.10:
                geometry_issues.append(f"{action_id}:leader_endpoint")
            if len(vertices) == 3 and math.dist(text.get("position", []), vertices[0]) > 8.0:
                geometry_issues.append(f"{action_id}:station_leader_spacing")
            angle_delta = abs((float(block.get("rotation", 0)) - float(expected["rotation"]) + math.pi) % (2*math.pi) - math.pi)
            if angle_delta > 1e-6 or abs(float(block.get("scale", 0)) - float(expected["scale"])) > 1e-6:
                geometry_issues.append(f"{action_id}:block_transform")
        return {"run_id": run_id, "snapshot_id": active["snapshot_id"], "entities": len(rows),
                "actions": len(by_action), "verified": bool(rows) and complete and count_ok and not geometry_issues,
                "geometry_issues": geometry_issues,
                "action_kinds": {key: sorted(value) for key, value in by_action.items()}}
