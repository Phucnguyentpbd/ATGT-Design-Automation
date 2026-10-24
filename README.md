# ATGT Design Automation — implementation foundation

**Hiện có knowledge, kiểm kê nguồn và lập phương án 3.1a/3.1b/4.4. Chưa có bộ thiết kế toàn tuyến, bộ ghi Civil hoặc xuất Excel hoàn chỉnh.**

Đã rà soát và sửa các lỗi về đo bóc, phiên bản quy tắc và dựng lại knowledge. Xem [báo cáo rà soát](docs/audit-and-rules-2026-10-24.md), [quy tắc vạch sơn](docs/marking-rules.md) và [hợp đồng làm việc cho agent](docs/agent-workflow.md).

Dùng trực tiếp `TEMPLATE_VACH_SON_ATGT_QCVN41_2024.dwg` và `VACH_SON_QCVN41_2024.lin` do người dùng cung cấp, không tạo thêm thư viện từ các dự án mẫu. Việc đọc cách gắn mũi tên/lý trình từ `BD TK ATGT DA DT.633.dwg` được người dùng dời sang lượt sau.

This repository is scaffolded from `docs/implementation-plan-v2.md` (24 Oct 2026). The plan is the implementation source of truth, including its Phase 1 approved-template update. Scope for automation: ordinary roads and divided roads outside urban areas; urban roads and expressways remain blocked. Source CAD, QCVN PDF, Excel template and sample approved projects are **not bundled**. Their original bytes are deliberately excluded from this public GitHub repository, though some files have been reviewed in private conversation attachments.

## What is implemented

- Typed Python contracts for locked sources, segments, sign faces/clusters, markings and quantity ledger.
- Fail-closed checks for road type, snapshot and evidence, sign identifiers with mandatory prefixes.
- Sign-face summary by full code, shape, real size and work type; **no post classification or post quantity**.
- Paint area from explicit verified painted intervals and station-range clipping (not guessed dash geometry).
- Missing/stale snapshot is represented as `None`, never a misleading zero.
- Unit tests for key invariants.
- **Phase 2 in progress:** read-only versioned DWG inventory, 14-pattern `.lin` parser, draft-only QCVN import, SQLite review/approval gate and Windows local library scan. **The user-uploaded Library.rar was inspected: 338 DWGs match the locked 69/122/33/83/31 group counts; all geometry/sign-code statuses remain unverified.** See [Phase 2 status](docs/phase2-progress.md).

## Quick start

```bash
python -m pip install -e ".[knowledge]" pytest
python -m pytest
```

### Scan the Windows AtgtPro library (read-only)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\scan_atgt_library.ps1
```

The scanner verifies counts and byte sizes against `data/source-locks/sign-library-summary.json`. The detailed inventory remains local at `local-manifests/atgt-signs.json`, with a separate `local-manifests/atgt-review-queue.json`. A metadata scan is **not** DWG geometry verification or license to draw. See [Phase 2 status](docs/phase2-progress.md).

## Next implementation gates

1. **Sources and regulatory knowledge**: ingest/verify original QCVN 41:2024 PDF (`84825A72C4605B65485F3D31A606525A9BC96C970A5200DEFC0781496DDBBD46`) and review every executable rule against original pages, tables and figures. Establish SQLite index and rule approval workflow.
2. **Asset catalog**: read/verify 338 sign DWGs from `AtgtPro/Library` (no renaming). Maintain full `sign_code` such as `P.102`, separate versioned `asset_id`, units, extents, orientation, provenance and CAD insertion tests. Marking DWG/LIN sources are already supplied; geometry still needs verification.
3. **Decision interface**: implement `atgt_search`, `atgt_get`, `atgt_evaluate_rules`, `atgt_resolve_asset`, `atgt_validate_plan` against approved rules; missing evidence must block only affected decisions.
4. **Civil 3D integration**: single writer using verified C# / Civil MCP; copy input DWG, batch execution, read-back and idempotency; no blind retry on timeout.
5. **Quantity export**: use the current workbook `Book2.xlsx` (SHA-256 `19672f2be596f471afbfeef0294b1831e1c148a14030dcc901f71f39f8d73985`) as a *copy*; preserve key layout, strip old values/external links, recalc in Excel, test print areas and manual post-column preservation by stable cluster IDs.
6. **End-to-end validation**: approved sample DWG+PDF, independent reviewer, at least 30 specialist cases, one ordinary and one divided road.

## Important exclusions

No QCVN rule is treated as verified merely because its numerical value appears in the plan. No real CAD writes or project quantities are attempted without original input sources and Civil 3D. No invented values, no imported sample quantities, no post/mast takeoff.

## Security

Do not commit proprietary approved drawings or copyrighted source standards without authorization, nor tokens or personal project data. Put local sources outside version control. See `.gitignore`.

## QCVN knowledge ingestion — 24 October 2026

The locked 403-page source PDF has been indexed locally (84 articles, 13 annexes, 502 mentioned sign codes, 50 marking codes), including 338 DWG review records and 14 LIN patterns. Original standards and CAD drawings are **not uploaded** to this public repository. The current database is rebuilt locally from the supplied sources. Current tests: **82 passed**. See [current audit](docs/audit-and-rules-2026-10-24.md); the earlier [knowledge coverage report](docs/knowledge-completion-2026-10-24.md) is historical.

Rebuild against your own approved source PDF and the reviewed 338-file catalog:

```bash
python -m pip install -e ".[knowledge]" pytest
python -m atgt.qcvn_ingest build --pdf QCVN_41_2024_mo_khoa.pdf --catalog atgt-sign-library-catalog.json --lin VACH_SON_QCVN41_2024.lin --out local-manifests/knowledge
python -m atgt.qcvn_ingest search --db local-manifests/knowledge/atgt-knowledge.sqlite --text P.102
```

**Not certified for automated design:** indexed QCVN evidence and filename-derived CAD code suggestions are distinct from expert-approved rules and geometrically verified DWG blocks.

## Thử lập phương án vạch sơn

```powershell
python -m atgt.planning_cli --kind edge --input examples/edge-contexts.json --lin "E:\TEMPLATE CV\BINH DO ATGT DU AN MAU\VACH_SON_QCVN41_2024.lin" --output local-manifests/edge-preview.json
python -m atgt.planning_cli --kind box44 --input examples/box44-contexts.json --output local-manifests/box44-preview.json
```

Ví dụ là dữ liệu giả định, không phải kết quả thiết kế dự án. Kết quả luôn có `cad_execution_allowed=false`; khoảng thiếu căn cứ có `status=blocked` và lý do. Vạch 4.4 tái sử dụng hàm phân loại từ skill của người dùng, với ngưỡng 5 m/30 m được ghi rõ là thực hành dự án. Đường đôi có dải phân cách cần xử lý theo từng phần xe chạy trước khi dùng quy tắc ô 4.4.
