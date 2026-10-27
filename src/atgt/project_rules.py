"""Load the single user-approved ATGT ruleset configured beside the standards."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re
import tomllib
from typing import Any


MAX_RULE_BYTES = 128 * 1024
RULESET_RE = re.compile(r"^ATGT-[A-Z0-9_-]{3,80}$")
ASSET_CATALOG_RE = re.compile(r"^ATGT-ASSETS-[A-Z0-9_-]{3,80}$")
REQUIRED_SECTIONS = {
    "source_precedence", "project_inputs", "priority", "sign_position",
    "junction_grouping", "marking_3_1a", "marking_3_1b", "marking_4_4",
    "annotation", "assets", "statistics", "cad_safety", "agent_behavior",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(data: dict[str, Any], dotted: str, expected: Any) -> None:
    value: Any = data
    for key in dotted.split("."):
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"Project rules missing required key: {dotted}")
        value = value[key]
    if value != expected:
        raise ValueError(
            f"Project rule {dotted}={value!r} is incompatible with the executable rules; "
            f"expected {expected!r}. Review and version the implementation before changing it.")


class ProjectRules:
    """Immutable startup snapshot with drift detection and bounded section reads."""

    def __init__(self, path: Path):
        self.path = path.resolve(strict=True)
        size = self.path.stat().st_size
        if not 1 <= size <= MAX_RULE_BYTES:
            raise ValueError(f"Project rules file must be 1..{MAX_RULE_BYTES} bytes")
        self.sha256 = digest(self.path)
        try:
            data = tomllib.loads(self.path.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeError) as exc:
            raise ValueError("Project rules file is not valid UTF-8 TOML") from exc
        if data.get("schema_version") != 1:
            raise ValueError("Project rules schema_version must be 1")
        ruleset_id = data.get("ruleset_id")
        if not isinstance(ruleset_id, str) or not RULESET_RE.fullmatch(ruleset_id):
            raise ValueError("Project ruleset_id must be a stable ATGT-* identifier")
        missing = sorted(REQUIRED_SECTIONS - set(data))
        if missing:
            raise ValueError("Project rules missing sections: " + ", ".join(missing))
        scope = data.get("scope")
        if not isinstance(scope, list) or not scope or set(scope) - {"ordinary", "divided_rural"}:
            raise ValueError("Project rules scope must contain only ordinary/divided_rural")
        assets = data["assets"]
        catalog_path = assets.get("asset_catalog") if isinstance(assets, dict) else None
        catalog_id = assets.get("asset_catalog_id") if isinstance(assets, dict) else None
        if (not isinstance(catalog_path, str) or not catalog_path.lower().endswith(".json") or
                not isinstance(catalog_id, str) or not ASSET_CATALOG_RE.fullmatch(catalog_id)):
            raise ValueError("Project rules must bind a versioned ATGT-ASSETS-* JSON catalog")

        # These values are executable invariants today. A changed TOML must not silently
        # disagree with code that writes CAD; updating one requires reviewing the other.
        for dotted, expected in {
            "source_precedence.qcvn_specific_overrides_user_rule": True,
            "priority.main_route_default": "priority",
            "priority.cross_roads_default": "non_priority",
            "priority.same_level_family": "W.205",
            "priority.non_priority_branch_family": "W.207",
            "sign_position.tcvn4054_s1_is_fallback_only_after_qcvn_search": True,
            "junction_grouping.group_when_consecutive_station_gap_is_less_than_s1": True,
            "junction_grouping.equal_to_s1_starts_new_group": True,
            "junction_grouping.all_non_priority_dense_group_codes": ["W.207d", "W.207e"],
            "junction_grouping.s501_length_from_sign_to_last_junction": True,
            "junction_grouping.s501_rounding_m": 10,
            "marking_3_1a.outer_edge_centerline_offset_m": 0.30,
            "marking_3_1a.median_edge_centerline_offset_m": 0.50,
            "marking_3_1b.linetype": "VACH_3.1B_0.6M",
            "marking_4_4.legacy_writer_allowed": False,
            "annotation.archetype_drawing": r"E:\TEMPLATE CV\BINH DO ATGT DU AN MAU\BD TK ATGT TAY VAN CANH.dwg",
            "annotation.excluded_archetype_drawing": "BD TK ATGT DA DT.633.dwg",
            "assets.sign_code_requires_prefix": True,
            "assets.asset_geometry_review_required_before_insert": True,
            "assets.agent_must_resolve_asset_id_before_import": True,
            "assets.agent_must_not_pass_arbitrary_asset_paths": True,
            "statistics.post_type_is_not_inferred": True,
            "statistics.post_quantity_is_not_automated": True,
            "cad_safety.source_dwg_must_not_be_saved": True,
            "cad_safety.distinct_work_copy_required": True,
            "cad_safety.one_writer_per_drawing": True,
            "cad_safety.readback_required_before_save": True,
            "agent_behavior.load_rules_at_start_of_every_task": True,
            "agent_behavior.do_not_repeat_rules_in_user_prompt": True,
        }.items():
            _require(data, dotted, expected)
        self.ruleset_id = ruleset_id
        self.data = data

    def assert_unchanged(self) -> None:
        if digest(self.path) != self.sha256:
            raise ValueError(
                "Configured project rules changed; restart after reviewing and versioning the ruleset")

    def get(self, section: str = "all") -> dict[str, Any]:
        self.assert_unchanged()
        if section == "all":
            return deepcopy(self.data)
        if section not in REQUIRED_SECTIONS:
            raise ValueError(
                "Unknown project-rules section; use all or one of: " +
                ", ".join(sorted(REQUIRED_SECTIONS)))
        return deepcopy(self.data[section])

    def summary(self) -> dict[str, Any]:
        self.assert_unchanged()
        return {
            "ruleset_id": self.ruleset_id,
            "sha256": self.sha256,
            "path": str(self.path),
            "schema_version": self.data["schema_version"],
            "scope": list(self.data["scope"]),
            "sections": sorted(REQUIRED_SECTIONS),
        }
