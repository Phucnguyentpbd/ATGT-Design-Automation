# ATGT project instructions

- Communicate in Vietnamese. Read `docs/audit-and-rules-2026-10-24.md` for the current implementation boundary.
- Initial scope: ordinary roads and divided roads outside urban areas. Evaluate each rule's narrower scope as well.
- Use the supplied `TEMPLATE_VACH_SON_ATGT_QCVN41_2024.dwg` and `VACH_SON_QCVN41_2024.lin`. Do not build another marking library from the sample projects.
- Sample drawings are references for annotation and project practice. They do not override QCVN. Reading their leader/station annotation was explicitly deferred by the user on 24 October 2026.
- The 4.4 classifier is reused from the user's skill. Read `docs/marking-rules.md` before extending it. Do not invoke the legacy skill writer: it deletes all entities on a layer, guesses minimum widths and uses a fixed MCP port.
- Distinguish source text, QCVN requirements, user practice, reviewed assets, proposed placements and read-back-verified CAD entities.
- Never make a draft rule executable by naming a file `approved`. Proposal APIs do not authorize a CAD writer.
- One writer per drawing. Verify the connected drawing's full identity and units. Preserve source drawings; use a distinct work copy. Do not retry a timed-out CAD write or save an active source DWG.
- Use native Curve/Alignment geometry. Curve distance, displayed chainage and the length of an offset marking are different quantities. Do not approximate curves using straight chords between sparse vertices.
- Full sign codes are required (`P.102`, `DP.135`, etc.). Quantity keys exclude poles. Preserve user-entered pole classification on Excel updates.
- Book2 export is implemented in `scripts/export_book2.py`; read `docs/book2-export.md` before changing its ledger or workbook contract. A verified flag is an upstream evidence contract, not independent proof that Civil was queried. Never report the synthetic example as project quantities.
- Keep PDF, DWG, LIN, XLSX, SQLite and detailed project evidence out of public Git. `local-manifests/` is ignored.
- MCP is read-only and source-bound. Read `docs/mcp-integration.md`; no tool may approve rules, write CAD or accept arbitrary filesystem paths. MCP client success does not prove the user's Orca/Antigravity session loaded it.
- Validation: `python -m pip install -e ".[knowledge,mcp]" pytest`, then `python -m pytest -q`. New regression tests must fail before the repair for the intended reason. Python tests are not live Civil/Excel acceptance.
