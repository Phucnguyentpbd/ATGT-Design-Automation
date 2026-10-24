# Phase 1 — Source intake status (updated 24/10/2026)

- **QCVN 41:2024/BGTVT:** original 403-page PDF identity confirmed; SHA-256 `84825a72c4605b65485f3d31a606525a9bc96c970a5200defc0781496ddbbd46` matches the plan.
- **Excel:** user confirms `Book2(1).xlsx` is the official sample (replacing the earlier workbook lock). Locked SHA-256: `19672f2be596f471afbfeef0294b1831e1c148a14030dcc901f71f39f8d73985`. Contains `KL VACH SON` and `THONG KE BIEN BAO ATGT`; formulas/links must be sanitized when exporting a new project.
- **Road design examples:** two sample DWG files received, but only their DWG header/fingerprints were verified, not their drawing geometry.
- **Marking source:** `TEMPLATE_VACH_SON_ATGT_QCVN41_2024.dwg` and `VACH_SON_QCVN41_2024.lin` received; the latter contains 14 parsed patterns. Neither is yet professionally approved as QCVN 2024-compliant.
- **Sign source:** AtgtPro/Library directory on Windows has been specified. The inventory script is implemented, but connection to the user's local D: directory is not available (CloudHarness MCP currently HTTP 404).

Raw proprietary DWG/PDF/XLSX sources are **not** committed to this public repository. See [Phase 2 progress](phase2-progress.md) and [Issue #2](../issues/2).
