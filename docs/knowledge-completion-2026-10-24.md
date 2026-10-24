# Knowledge ingestion delivery — 24/10/2026

## Scope completed as data ingestion

The user's locked QCVN 41:2024 PDF was processed locally into an indexed SQLite knowledge database with full source text (not committed here). An exact-match source hash gate refuses a different PDF version. The deliverable SQLite, detailed indices, code and 338-row review queue were packaged separately for the user.

See the public, non-source **[coverage report](../data/knowledge/coverage-2026-10-24.json)**.

| Coverage | Result |
|---|---:|
| QCVN PDF pages indexed | 403 / 403 |
| Articles indexed | 84 / 84 |
| Annexes indexed | 13 |
| Sign code mentions grouped by code | 502 |
| Marking codes observed in Annex G | 50 |
| Clause anchors | 412 |
| Figure/page references | 318 |
| DWG source assets received/cataloged | 338 |
| Unique DWG filename-based code suggestions | 326 |
| Ambiguous filename-based code suggestions | 9 |
| Unmatched filename-based code suggestions | 3 |
| LIN patterns parsed | 14 |
| Structured source-referenced rule drafts | 19 |
| CAD-executable expert-approved rules | **0** |
| Local structural ingestion tests | **38 passed** |

These counts measure **indexing and traceability**. A code mention in QCVN is not proof of a unique sign type, and a name-based DWG match is not a verified geometry or dimension. Full-text indexing does not certify numeric values embedded in tables or drawings.

## Repository entrypoints

- `src/atgt/qcvn_ingest.py`: reproducible source-locked PDF and DWG catalog ingestion into local SQLite FTS5.
- `src/atgt/knowledge.py`: draft/approved rule store; only explicitly approved versions are usable.
- `src/atgt/library_review.py`: DWG source-lock consistency and human review flags.
- `data/rules/qcvn41-core-reference-drafts.json`: 19 draft structured constraints, intentionally not enabled for automatic CAD.
- `tests/test_qcvn_ingest.py`: CI structural checks for codes and annexes.
- `data/source-locks/sign-library-summary.json`: locked inventory of the user's 338 DWGs.

## Rebuild on the user's machine

Install Python 3.10+ and open the repository root:

```powershell
py -m pip install -e ".[knowledge]" pytest
py -m atgt.qcvn_ingest build --pdf "D:\\Sources\\QCVN_41_2024_mo_khoa.pdf" --catalog "D:\\Sources\\atgt-sign-library-catalog.json" --lin "D:\\Sources\\VACH_SON_QCVN41_2024.lin" --out "local-manifests\\knowledge"
py -m atgt.qcvn_ingest search --db "local-manifests\\knowledge\\atgt-knowledge.sqlite" --text "P.102"
py -m pytest -q
```

Use the private downloadable Knowledge archive supplied in this conversation for the **already-built** complete index and evidence links, including original-text pages, source reference drafts and specialist review queue. The standalone archive also includes a fuller extraction and reporting program with stricter ingestion checks; the repository importer is a lightweight reproducible entrypoint.

## What must not be misrepresented as completed engineering approval

1. A compatible CAD tool must still inspect the geometry, dimensions, insertion points, units, rotations, layers and attributes of the 338 original DWGs.
2. Source figure/table parameters and all 19 executable-rule candidates need specialist technical review; the rule store must remain fail-closed pending approval.
3. Civil 3D placement and physical takeoff must be independently verified against the actual input DWG and approved design documents.
4. The workbook template is user-approved (`Book2(1).xlsx`) but no new project quantities may be inferred from its example contents.

**Current release status:** full-text knowledge-indexing package completed; engineering rule certification and automated CAD production remain pending independent validation.
