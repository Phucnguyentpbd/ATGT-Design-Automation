# ATGT Design Automation — implementation foundation

**Status: prototype core only; NOT an approved automatic road-safety design system.**

This repository is scaffolded from `docs/implementation-plan-v2.md` (24 Oct 2026). The plan is the implementation source of truth, including its Phase 1 approved-template update. Scope for automation: ordinary roads and divided roads outside urban areas; urban roads and expressways remain blocked. Source CAD, QCVN PDF, Excel template and sample approved projects are **not bundled** because the plan only supplies Windows paths and fingerprints, not their bytes.

## What is implemented

- Typed Python contracts for locked sources, segments, sign faces/clusters, markings and quantity ledger.
- Fail-closed checks for road type, snapshot and evidence, sign identifiers with mandatory prefixes.
- Sign-face summary by full code, shape, real size and work type; **no post classification or post quantity**.
- Paint area from explicit verified painted intervals and station-range clipping (not guessed dash geometry).
- Missing/stale snapshot is represented as `None`, never a misleading zero.
- Unit tests for key invariants.

## Quick start

```bash
python -m pip install -e . pytest
python -m pytest
```

## Next implementation gates

1. **Sources and regulatory knowledge**: ingest/verify original QCVN 41:2024 PDF (`84825A72C4605B65485F3D31A606525A9BC96C970A5200DEFC0781496DDBBD46`) and review every executable rule against original pages, tables and figures. Establish SQLite index and rule approval workflow.
2. **Asset catalog**: read/verify 338 sign DWGs from `AtgtPro/Library` (no renaming). Maintain full `sign_code` such as `P.102`, separate versioned `asset_id`, units, extents, orientation, provenance and CAD insertion tests; identify a source for marking assets.
3. **Decision interface**: implement `atgt_search`, `atgt_get`, `atgt_evaluate_rules`, `atgt_resolve_asset`, `atgt_validate_plan` against approved rules; missing evidence must block only affected decisions.
4. **Civil 3D integration**: single writer using verified C# / Civil MCP; copy input DWG, batch execution, read-back and idempotency; no blind retry on timeout.
5. **Quantity export**: use the approved workbook `Book2(1).xlsx` (SHA-256 `97F12717B4479187E93E8889DA0DDAF8098DC471609F7F52D94ABF849DB0B43D`) as a *copy*; preserve key layout, strip old values/external links, recalc in Excel, test print areas and manual post-column preservation by stable cluster IDs.
6. **End-to-end validation**: approved sample DWG+PDF, independent reviewer, at least 30 specialist cases, one ordinary and one divided road.

## Important exclusions

No QCVN rule is treated as verified merely because its numerical value appears in the plan. No real CAD writes or project quantities are attempted without original input sources and Civil 3D. No invented values, no imported sample quantities, no post/mast takeoff.

## Security

Do not commit proprietary approved drawings or copyrighted source standards without authorization, nor tokens or personal project data. Put local sources outside version control. See `.gitignore`.
