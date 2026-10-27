"""Guarded local MCP for Civil ATGT work copies, annotations and markings."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr

from .cad_session import CadConfig, CadSessionService
from .civil_rpc import CivilRpcClient


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


SafeId = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")]
AssetId = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9:_.-]{2,159}$")]


class SessionInput(Input):
    session_id: SafeId


class VerifyInput(Input):
    session_id: SafeId
    run_id: SafeId


class InventoryInput(Input):
    max_groups: Annotated[StrictInt, Field(ge=1, le=200)] = 80


LayerName = Annotated[StrictStr, Field(min_length=1, max_length=255)]


class DeclaredLayerSurveyInput(Input):
    snapshot_id: Annotated[StrictStr, Field(pattern=r"^live-[0-9a-f]{20}$")]
    centerline_layers: list[LayerName] = Field(min_length=1, max_length=20)
    road_edge_layers: list[LayerName] = Field(min_length=1, max_length=40)
    limit: Annotated[StrictInt, Field(ge=1, le=200)] = 100
    offset: Annotated[StrictInt, Field(ge=0, le=10000)] = 0


class NativeGeometryInput(Input):
    handles: list[Annotated[StrictStr, Field(pattern=r"^[0-9A-Fa-f]{1,16}$")]] = Field(
        min_length=1, max_length=50)


class AssetListInput(Input):
    kind: Literal["sign", "marking_block"] | None = None
    code: Annotated[StrictStr, Field(min_length=3, max_length=40)] | None = None
    status: Literal["review_required", "approved_for_insert", "retired"] | None = None
    limit: Annotated[StrictInt, Field(ge=1, le=100)] = 50
    offset: Annotated[StrictInt, Field(ge=0, le=10000)] = 0


class AssetImportInput(Input):
    session_id: SafeId
    import_id: SafeId
    asset_ids: list[AssetId] = Field(min_length=1, max_length=50)


class AssetImportVerifyInput(Input):
    session_id: SafeId
    import_id: SafeId


class AnnotationAction(Input):
    action_id: SafeId
    sign_code: Annotated[StrictStr, Field(pattern=r"^(?:P|W|R|I|DP|S|IE|RE)\.[0-9]+[A-Za-z]?$", max_length=20)]
    asset_id: AssetId
    station_text: Annotated[StrictStr, Field(pattern=r"(?i)^km\d+\+\d+(?:[.,]\d+)?$", max_length=40)]
    x: StrictFloat
    y: StrictFloat
    z: StrictFloat = 0.0
    rotation: StrictFloat = 0.0
    scale_multiplier: Annotated[StrictFloat, Field(ge=0.01, le=100)] = 1.0
    block_layer: Annotated[StrictStr, Field(min_length=1, max_length=100)] = "BIEN BAO"


class AnnotationBatchInput(Input):
    session_id: SafeId
    run_id: SafeId
    actions: list[AnnotationAction] = Field(min_length=1, max_length=50)


class MarkingVertex(Input):
    x: StrictFloat
    y: StrictFloat
    bulge: StrictFloat = 0.0


class MarkingPath(Input):
    closed: StrictBool
    vertices: list[MarkingVertex] = Field(min_length=2, max_length=500)


class MarkingAction(Input):
    action_id: SafeId
    proposal_id: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    marking_code: Annotated[StrictStr, Field(pattern=r"^(?:3\.1a|3\.1b|4\.4)$")]
    layer: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    linetype: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    width_m: Annotated[StrictFloat, Field(ge=0.15, le=0.40)]
    native_curve_geometry_verified: StrictBool
    geometry_evidence: Annotated[StrictStr, Field(min_length=1, max_length=500)]
    paths: list[MarkingPath] = Field(min_length=1, max_length=3)


class MarkingBatchInput(Input):
    session_id: SafeId
    run_id: SafeId
    actions: list[MarkingAction] = Field(min_length=1, max_length=50)


class MarkingBlockAction(Input):
    action_id: SafeId
    proposal_id: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    marking_code: Annotated[StrictStr, Field(pattern=r"^[1-9]\.[0-9]{1,2}(?:[A-Za-z])?$")]
    asset_id: AssetId
    x: StrictFloat
    y: StrictFloat
    z: StrictFloat = 0.0
    alignment_tangent_rad: StrictFloat
    scale_multiplier: Annotated[StrictFloat, Field(ge=0.01, le=100)] = 1.0
    layer: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    geometry_evidence: Annotated[StrictStr, Field(min_length=1, max_length=500)]


class MarkingBlockBatchInput(Input):
    session_id: SafeId
    run_id: SafeId
    actions: list[MarkingBlockAction] = Field(min_length=1, max_length=50)


def create_server(service: CadSessionService) -> FastMCP:
    mcp = FastMCP("atgt_cad_mcp", instructions=(
        "Guarded ATGT CAD writer. Always call atgt_cad_status first. Create and activate a distinct "
        "work copy before any write. Resolve catalog assets, import by asset_id, then place; caller "
        "paths and guessed block names are forbidden. A write batch is 1..50 actions, run_id is "
        "single-use, and every batch is read back through ATGT_AGENT XData. Never retry a timed-out "
        "write automatically."))
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                           idempotentHint=True, openWorldHint=False)
    mutate = ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                             idempotentHint=False, openWorldHint=False)

    @mcp.tool(name="atgt_cad_status", annotations=read)
    async def atgt_cad_status() -> dict[str, Any]:
        """Inspect the Civil listener and exact active drawing identity without modifying CAD."""
        return await service.status()

    @mcp.tool(name="atgt_cad_inventory_semantics", annotations=read)
    async def atgt_cad_inventory_semantics(params: InventoryInput) -> dict[str, Any]:
        """Group model-space entities by layer/type and expose only unverified semantic hints.

        Results are count-sorted and bounded. A hint such as centerline_candidate is discovery
        metadata, never evidence that the layer actually carries that road role.
        """
        return await service.inventory_semantics(params.max_groups)

    @mcp.tool(name="atgt_cad_survey_declared_layers", annotations=read)
    async def atgt_cad_survey_declared_layers(params: DeclaredLayerSurveyInput) -> dict[str, Any]:
        """Survey exact centerline and road-edge layer names declared by the user for this drawing.

        The snapshot must still match. Layer roles come from user input, not name heuristics;
        individual entities and their left/right/main/branch topology remain unverified. Results
        are paginated and read-only.
        """
        return await service.survey_declared_layers(
            params.snapshot_id, params.centerline_layers, params.road_edge_layers,
            params.limit, params.offset)

    @mcp.tool(name="atgt_cad_extract_native_geometry", annotations=read)
    async def atgt_cad_extract_native_geometry(params: NativeGeometryInput) -> dict[str, Any]:
        """Read exact native geometry for 1..50 reviewed handles without changing the drawing.

        Line, Arc, Circle and lightweight Polyline have exact representations. Civil Alignment
        returns its station range; other curve types are explicitly marked for a later native
        offset/convert step and must not be treated as chord-approximated marking geometry.
        """
        return await service.extract_native_geometry(params.handles)

    @mcp.tool(name="atgt_cad_list_assets", annotations=read)
    async def atgt_cad_list_assets(params: AssetListInput) -> dict[str, Any]:
        """List catalog assets and approval status without accepting filesystem paths."""
        return service.list_assets(params.kind, params.code, params.status,
                                   params.limit, params.offset)

    @mcp.tool(name="atgt_cad_prepare_work_copy", annotations=mutate)
    async def atgt_cad_prepare_work_copy(params: SessionInput) -> dict[str, Any]:
        """Create one new DWG from the active source's in-memory state; source stays active and unsaved."""
        return await service.prepare_work_copy(params.session_id)

    @mcp.tool(name="atgt_cad_activate_work_copy", annotations=mutate)
    async def atgt_cad_activate_work_copy(params: SessionInput) -> dict[str, Any]:
        """Open and activate the session work copy. Refuses arbitrary filesystem paths."""
        return await service.activate_work_copy(params.session_id)

    @mcp.tool(name="atgt_cad_restore_source_active", annotations=mutate)
    async def atgt_cad_restore_source_active() -> dict[str, Any]:
        """Make the configured source drawing active again without saving or closing any drawing."""
        return await service.restore_source_active()

    @mcp.tool(name="atgt_cad_sync_work_copy_units", annotations=mutate)
    async def atgt_cad_sync_work_copy_units(params: SessionInput) -> dict[str, Any]:
        """Make the active isolated copy use the source INSUNITS, save it, and read the value back."""
        return await service.sync_work_copy_units(params.session_id)

    @mcp.tool(name="atgt_cad_import_marking_linetype", annotations=mutate)
    async def atgt_cad_import_marking_linetype(params: SessionInput) -> dict[str, Any]:
        """Import only reviewed VACH_3.1B_0.6M from the configured template and verify 0.6/-0.6."""
        return await service.import_marking_linetype(params.session_id)

    @mcp.tool(name="atgt_cad_import_assets", annotations=mutate)
    async def atgt_cad_import_assets(params: AssetImportInput) -> dict[str, Any]:
        """Import only approved, hash-locked catalog assets into the active verified work copy.

        Whole sign DWGs become stable block definitions; reviewed named marking blocks are cloned
        from the configured template. Reusing import_id performs read-back reconciliation and never
        blindly repeats a timed-out write.
        """
        return await service.import_assets(params.session_id, params.import_id, params.asset_ids)

    @mcp.tool(name="atgt_cad_verify_asset_import", annotations=read)
    async def atgt_cad_verify_asset_import(params: AssetImportVerifyInput) -> dict[str, Any]:
        """Read block-table ownership/hash data for one staged asset import."""
        return await service.verify_asset_import(params.session_id, params.import_id)

    @mcp.tool(name="atgt_cad_save_verified_work_copy", annotations=mutate)
    async def atgt_cad_save_verified_work_copy(params: SessionInput) -> dict[str, Any]:
        """Save only the active session copy, after at least one batch passed independent read-back."""
        return await service.save_verified_work_copy(params.session_id)

    @mcp.tool(name="atgt_cad_apply_sign_annotations", annotations=mutate)
    async def atgt_cad_apply_sign_annotations(params: AnnotationBatchInput) -> dict[str, Any]:
        """Place sign block + three-vertex leader + station text from the reviewed TAY VAN CANH archetype.

        Each asset_id must have a verified import receipt in this session. The MCP derives the block
        name, reviewed scale and asset hash; the agent cannot guess them. A single-use run plan is
        recorded before the write and read-back must find one text, leader and block per action.
        """
        return await service.apply_annotation_batch(
            params.session_id, params.run_id,
            [action.model_dump(mode="python") for action in params.actions])

    @mcp.tool(name="atgt_cad_apply_markings", annotations=mutate)
    async def atgt_cad_apply_markings(params: MarkingBatchInput) -> dict[str, Any]:
        """Write reviewed 3.1a/3.1b or simple 4.4 polylines with exact vertices and arc bulges.

        The caller must supply geometry read from native curves, not sparse chord approximations.
        Simple 4.4 is exactly one closed outline plus two open diagonals. All paths receive
        ATGT_AGENT ownership data and must pass independent read-back.
        """
        return await service.apply_marking_batch(
            params.session_id, params.run_id,
            [action.model_dump(mode="python") for action in params.actions])

    @mcp.tool(name="atgt_cad_apply_marking_blocks", annotations=mutate)
    async def atgt_cad_apply_marking_blocks(params: MarkingBlockBatchInput) -> dict[str, Any]:
        """Place imported 7.6/9.3-style marking blocks by asset_id and alignment tangent.

        Catalog scale and rotation offset are applied inside the writer. Every BlockReference keeps
        asset hash ownership data and must pass independent position/transform read-back.
        """
        return await service.apply_marking_block_batch(
            params.session_id, params.run_id,
            [action.model_dump(mode="python") for action in params.actions])

    @mcp.tool(name="atgt_cad_verify_run", annotations=read)
    async def atgt_cad_verify_run(params: VerifyInput) -> dict[str, Any]:
        """Read back ATGT-owned CAD entities for a run without trusting the plan or prior receipt."""
        return await service.verify_run(params.session_id, params.run_id)

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--marking-template", required=True, type=Path)
    parser.add_argument("--sign-library", required=True, type=Path)
    parser.add_argument("--asset-catalog", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8070)
    parser.add_argument("--connect-timeout", type=float, default=5)
    parser.add_argument("--command-timeout", type=float, default=30)
    args = parser.parse_args()
    rpc = CivilRpcClient(args.host, args.port, args.connect_timeout, args.command_timeout)
    service = CadSessionService(CadConfig(
        args.expected_source, args.output_root, args.marking_template,
        args.sign_library, args.asset_catalog), rpc)
    create_server(service).run(transport="stdio")


if __name__ == "__main__":
    main()
