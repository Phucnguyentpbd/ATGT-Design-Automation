# MCP ATGT cục bộ — 25/10/2026

## MCP tri thức `atgt`

MCP chạy qua `stdio`, dùng SDK Python và các hàm đã có trong repo. Đây là bộ công cụ đọc nguồn/lập đề xuất, chưa phải bộ điều khiển Civil. Không cung cấp lệnh ghi CAD, tự duyệt rule, đọc file tùy ý, chạy shell hay sửa SQLite qua lời gọi công cụ.

Chọn `stdio` cho máy hiện tại vì host khởi chạy tiến trình trực tiếp, không phải giữ một cổng HTTP mới hoặc một dịch vụ mạng. Có thể mở nhiều phiên đọc cùng bộ nguồn. Phần ghi Civil sau này vẫn cần một bộ ghi duy nhất theo bản vẽ. SDK được giới hạn `mcp>=1.28.1,<2`, tránh đổi API lớn ngoài dự kiến. Tham khảo [SDK chính thức v1.28.1](https://github.com/modelcontextprotocol/python-sdk/tree/v1.28.1) và [quy định stdio](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).

| Công cụ | Nhiệm vụ | Giới hạn kết quả |
|---|---|---|
| `atgt_status` | Mã nguồn, số trang/tài sản, phạm vi triển khai | Phân biệt sẵn sàng đọc với CAD đã nghiệm thu |
| `atgt_get_project_rules` | Nạp toàn bộ ruleset dự án hoặc một section | Trả `ruleset_id`/SHA; quy tắc user không được giả thành trích dẫn QCVN |
| `atgt_search` | Tìm cụm từ/mã trong QCVN | Mặc định 5, tối đa 20 kết quả; có phân trang |
| `atgt_get` | Lấy trang PDF, chỉ mục biển hoặc vạch | Văn bản từng cửa sổ tối đa 6.000 ký tự |
| `atgt_resolve_asset` | Tìm DWG ứng viên theo mã đầy đủ | Không biến gợi ý từ tên file thành block đã duyệt |
| `atgt_evaluate_rules` | Đề xuất vị trí biển, chuỗi W.205/W.207, 3.1a/3.1b hoặc 4.4 đơn giản | Tối đa 50 đối tượng hoặc 10 hành lang/nhóm nút; cùng một snapshot |
| `atgt_validate_plan` | Tính lại và đối chiếu phương án nhận được | Bắt thay đổi thông số/nguồn; không thay thế thẩm tra hình học |

Đầu vào có schema cụ thể để agent biết trường nào phải đo hoặc cung cấp căn cứ. Chuỗi `"true"` không được nhận như giá trị xác minh `true`. Giá trị vô hạn/NaN, thuộc tính lạ và lô quá lớn bị từ chối. Không tự chọn vạch 4.4 chỉ vì tìm thấy một lối mở.

Kết quả luôn có `cad_execution_allowed=false`, mã nguồn PDF/SQLite/LIN và mức độ xác minh. Văn bản QCVN được trả về như dữ liệu tham khảo, không phải chỉ dẫn hệ thống cho agent. Cần đọc hình gốc khi điều kiện áp dụng phụ thuộc hình/bảng.

## Cài môi trường riêng

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[knowledge,mcp]" pytest
.\.venv\Scripts\python.exe -m pytest -q
```

Không cài các phụ thuộc này đè vào Python đang chạy MCP Civil hoặc runtime tài liệu. Trên máy triển khai, môi trường `.venv` đã được tạo và đã chạy được MCP.

Chỉ mục cũ phải dựng lại bằng `atgt.qcvn_ingest` để có metadata khóa PDF. Nếu thiếu metadata, server dừng với hướng dẫn dựng lại; không tự sửa DB khi khởi động. Đường dẫn SQLite, LIN và PDF TCVN 4054 là cấu hình khi khởi động, không phải tham số để agent trỏ tới file bất kỳ. Thiếu PDF TCVN không làm hỏng tra cứu QCVN/vạch, nhưng mọi đề xuất dùng tầm nhìn hãm xe bị chặn.

```powershell
.\.venv\Scripts\python.exe -m atgt.mcp_server `
  --db 'D:\AGENT_AI\ATGT-Design-Automation\local-manifests\knowledge\atgt-knowledge.sqlite' `
  --lin 'E:\TEMPLATE CV\BINH DO ATGT DU AN MAU\VACH_SON_QCVN41_2024.lin' `
  --tcvn4054 'D:\DOCUMENT\TCVN\TIEU CHUAN THIET KE\TCVN 4054-2005_DUONG O TO YEU CAU THIET KE.pdf' `
  --rules 'D:\DOCUMENT\TCVN\TIEU CHUAN TK ATGT\ATGT_PROJECT_RULES.toml'
```

Lệnh trên là tiến trình chờ host MCP gửi yêu cầu; không in menu giao diện. Nhật ký đi qua stderr, stdout dành cho giao thức.

## Kết nối vào host

`examples/mcp.atgt.windows.json` chứa một mục `mcpServers.atgt` với đường dẫn tuyệt đối trên máy hiện tại. Chỉ hợp nhất mục `atgt` vào cấu hình host đã xác định, giữ các server khác. Không thay toàn bộ file cấu hình bằng ví dụ. Nếu cài ở máy khác, đổi đường dẫn repo, môi trường Python, DB và LIN tương ứng.

Orca có thể điều phối agent dùng MCP này thông qua cấu hình MCP của agent. Việc client SDK kết nối thành công không chứng minh phiên Orca/Antigravity đang chạy đã nhận cấu hình mới; cần làm mới danh sách công cụ hoặc mở phiên agent mới theo cơ chế của host. Không khởi động thêm agent chỉ để tuyên bố đã triển khai.

### Antigravity CLI, OpenCode và Codex trong Orca

Đã gắn cùng mục `atgt` trên máy triển khai ngày 25/10/2026:

| Host | Cấu hình dùng trên máy hiện tại | Bằng chứng |
|---|---|---|
| Antigravity CLI | `%USERPROFILE%\.gemini\config\mcp_config.json` | `agy mcp list` nhận `atgt`, trạng thái enabled |
| OpenCode | `%USERPROFILE%\.config\opencode\opencode.jsonc` | `opencode debug config` nhận đúng cấu hình; `opencode mcp list` báo connected |
| Codex | `%USERPROFILE%\.codex\config.toml` | `codex mcp get atgt --json` nhận đúng mục stdio, enabled |
| Codex runtime của Orca | `%APPDATA%\orca\codex-runtime-home\home\config.toml` | Chạy `codex mcp get atgt --json` với đúng `CODEX_HOME` cũng nhận mục này |

Các đường dẫn trên đã được kiểm tra ở máy triển khai, không phải quy ước áp dụng cho mọi phiên bản Orca. Orca hiện không có lệnh ghi đè chương trình hoặc biến môi trường riêng cho ba agent này. Nếu sau này chuyển profile hoặc tài khoản được Orca quản lý, cần xác nhận lại cấu hình thực sự được nạp.

Đã sao lưu từng file trước khi sửa và giữ cấu hình các MCP có sẵn. Antigravity có UTF-8 BOM làm `agy mcp list` không phân tích được JSON; đã bỏ BOM và kiểm tra lại. Với OpenCode, mục local dùng `command` là một mảng gồm chương trình và các đối số, `environment` cho biến môi trường, `enabled: true`, `timeout: 20000`; không chép nguyên cấu trúc `mcpServers` vào OpenCode. Với Codex, dùng lệnh native `codex mcp add` để ghi TOML.

Client SDK đã khởi chạy server từ từng bản cấu hình thực tế, ở thư mục ngoài repo và không thêm `PYTHONPATH`. Cả bốn binding Antigravity, OpenCode, Codex và Codex-Orca đều nhận đủ bảy công cụ. Ruleset hiện là `ATGT-USER-RULES-20261026-V2`, SHA-256 `2e562e678fd2d50055238eaba053b26f6669417b5fe3da95353f0e24ea0b5168`; V2 bổ sung đường dẫn/id catalog và cấm agent truyền đường dẫn asset tùy ý.

Phép kiểm tra Codex app-server dùng runtime Orca hết thời gian sau 30 giây; nhật ký đồng thời ghi lỗi 401 ở các yêu cầu tài khoản/plugin/model. Đã dừng tiến trình kiểm tra và không thay đăng nhập. Chưa chứng minh đây là nguyên nhân của timeout, cũng chưa coi đó là lỗi ATGT. Orca đang đóng khi kiểm tra; chưa có nghiệm thu phiên agent trong UI. Không có lượt gọi model hay thao tác Civil nào trong đợt gắn cấu hình này.

Khi mở lại Orca, mở phiên agent mới tại repo này để nhận cấu hình. Nhiệm vụ đầu tiên có thể dùng:

> Dùng MCP atgt tra căn cứ P.102 và vạch 3.1a/3.1b. Nếu cần ghi CAD, gọi atgt-cad status, chỉ làm trên work copy, nhập linetype 3.1b từ template khi cần và chỉ lưu sau read-back đạt.

Bằng chứng và đường dẫn bản sao lưu được giữ cục bộ trong `local-manifests/mcp/deployment.json`, `client-bindings-evidence.json` và `native-host-evidence.json`; không đưa cấu hình tài khoản lên Git.

## Luồng gọi cho agent

1. `atgt_status`: giữ mã nguồn và kiểm tra đúng phạm vi.
2. `atgt_get_project_rules(section="all")`: nạp ruleset một lần ở đầu task, giữ `ruleset_id` và SHA trong toàn bộ phương án; không yêu cầu user lặp quy tắc trong prompt.
3. `atgt_search` rồi `atgt_get`: lấy căn cứ theo mã/điều/trang. Khi có phân trang, dùng `next_offset` để lấy phần còn lại.
4. `atgt_resolve_asset`: xác định ứng viên và các kiểm tra hình học còn thiếu.
5. Gọi `atgt_cad_status`, rồi `atgt_cad_survey_declared_layers` với layer tim/mép do user khai báo cho đúng snapshot. Dùng `atgt_cad_extract_native_geometry` cho handle đã chọn; chưa xác nhận topology thì chưa lập phương án toàn tuyến.
6. Sau khi đo bình đồ, gọi `atgt_evaluate_rules` với ngữ cảnh có snapshot, tim, mép, loại đường và bằng chứng chuyển hướng/không dừng. Với biển, truyền tốc độ thiết kế, chiều xe chạy, station range, kết quả tra QCVN và bằng chứng ưu tiên/hình học; xem [quy tắc vị trí biển](sign-placement-rules.md).
7. Gửi cả ngữ cảnh gốc và kết quả nhận được vào `atgt_validate_plan`. `ready_for_geometry_review=true` nghĩa là đề xuất nhất quán, vẫn cần thẩm tra hình học và CAD.
8. Gọi `atgt_cad_list_assets`, chọn đúng `asset_id` có `approved_for_insert`; tạo/khóa work copy, đồng bộ đơn vị, gọi `atgt_cad_import_assets` và đọc lại bằng `atgt_cad_verify_asset_import`.
9. Đặt cụm biển hoặc block vạch bằng `asset_id`, hoặc ghi polyline theo batch tối đa 50 đối tượng; gọi `atgt_cad_verify_run`. Chỉ sau khi mọi import/run đạt mới gọi lưu.
10. Đo bóc từ các đối tượng đã đọc lại, đưa ledger `verified` sang bộ xuất Book2. Hiện chưa có bộ tự tạo ledger dự án thật; tuyệt đối không tạo khối lượng trực tiếp từ proposal.

## Đã kiểm tra

```powershell
.\.venv\Scripts\python.exe scripts/check_mcp.py `
  --db local-manifests/knowledge/atgt-knowledge.sqlite `
  --lin 'E:\TEMPLATE CV\BINH DO ATGT DU AN MAU\VACH_SON_QCVN41_2024.lin' `
  --tcvn4054 'D:\DOCUMENT\TCVN\TIEU CHUAN THIET KE\TCVN 4054-2005_DUONG O TO YEU CAU THIET KE.pdf' `
  --rules 'D:\DOCUMENT\TCVN\TIEU CHUAN TK ATGT\ATGT_PROJECT_RULES.toml' `
  --output local-manifests/mcp/live-probe.json
```

Phép kiểm tra mới khởi chạy subprocess MCP thật, bắt tay, liệt kê và gọi cả bảy công cụ trên bộ nguồn thật, gồm ruleset đã khóa. Dữ liệu giả định chứng minh ba khoảng vạch mép, một khoảng thiếu căn cứ bị chặn, một nhóm ngã tư tạo một ô 4.4, tốc độ 60 km/h dùng S1 = 75 m và chuỗi W.207 tạo W.207d + S.501 = 130 m. P.102 trả về đúng ứng viên `Bien_Cam/102.dwg`, trạng thái vẫn chưa xác minh.

Toàn repo đạt 127 kiểm thử trong môi trường riêng; MCP SDK thực tế 1.30.0, Pydantic 2.14.1. Đã sửa lỗi tokenizer bỏ sót tìm không dấu `bien cam`/`mat vong` khi nguồn là `biển cấm`/`mắt võng`; vẫn ưu tiên mã đầy đủ hoặc từ khóa có dấu (đ/ d chưa được đồng nhất). Một cảnh báo chuyển đổi API `fitz` từ PyMuPDF 2.0 không làm hỏng phép kiểm tra; chưa coi cảnh báo đó là lỗi của dữ liệu QCVN.

Kiểm tra qua giao thức trên fixture độc lập: phân trang không trùng, lấy cửa sổ văn bản, không nhận đường dẫn thay số trang, không nhận FTS/SQL từ người gọi, từ chối xác minh kiểu chuỗi, lô quá lớn, trộn snapshot, phương án bị thay và nguồn bị sửa giữa phiên. Các lời gọi đọc giữ nguyên byte DB.

Đây là nghiệm thu giao thức MCP và quy tắc trên dữ liệu giả định. Bộ câu hỏi `evals/mcp-atgt.xml` dành cho đánh giá agent; chưa tuyên bố đã chạy một đợt đánh giá LLM độc lập.

## MCP thực thi `atgt-cad`

`atgt-cad` là tiến trình stdio riêng, kết nối listener Civil qua loopback. Cấu hình mẫu ở `examples/mcp.atgt-cad.windows.json` khóa nguồn TÂY VẠN CANH, thư mục đầu ra, endpoint `127.0.0.1:8070` và timeout 30 giây. Nó không làm `cad_execution_allowed` của MCP tri thức thành true.

| Tool | Vai trò |
|---|---|
| `atgt_cad_status` | Đọc listener, đường dẫn active, DBMOD, đơn vị, extents, số object và snapshot |
| `atgt_cad_inventory_semantics` | Gom model space theo layer/type, trả role hint chưa xác minh và tối đa 200 nhóm |
| `atgt_cad_survey_declared_layers` | Nhận layer tim/mép do user khai báo theo snapshot; kiểm tra thiếu/rỗng/xung đột, phân trang entity khớp |
| `atgt_cad_extract_native_geometry` | Đọc geometry native chính xác theo 1–50 handle; không biến proxy/generic curve thành chord giả |
| `atgt_cad_list_assets` | Liệt kê catalog theo mã/loại/trạng thái; không nhận đường dẫn file |
| `atgt_cad_prepare_work_copy` | Chụp trạng thái trong bộ nhớ sang DWG mới, không save nguồn |
| `atgt_cad_activate_work_copy` | Chỉ mở DWG thuộc session đã tạo |
| `atgt_cad_restore_source_active` | Đưa nguồn cấu hình về active, không save/close |
| `atgt_cad_sync_work_copy_units` | Đồng bộ INSUNITS bản sao theo nguồn và đọc lại |
| `atgt_cad_import_marking_linetype` | Nhập riêng 3.1b 0,6/0,6 từ template cấu hình và kiểm tra pattern |
| `atgt_cad_import_assets` | Import 1–50 asset đã duyệt/hash-lock; gọi lại cùng import id chỉ reconcile |
| `atgt_cad_verify_asset_import` | Đọc lại block definition, ownership, asset id/hash/code/kind |
| `atgt_cad_apply_sign_annotations` | Ghi lô 1–50 cụm block+leader+station theo asset id và archetype chuẩn |
| `atgt_cad_apply_markings` | Ghi polyline 3.1a/3.1b/4.4 đã có vertex+bulge xác minh; tối đa 50 path |
| `atgt_cad_apply_marking_blocks` | Đặt block vạch 7.6/9.3 theo asset id, vị trí và tiếp tuyến tim |
| `atgt_cad_verify_run` | Đọc XData và kiểm tra hình học độc lập |
| `atgt_cad_save_verified_work_copy` | Chỉ save bản sao khi đã có run read-back đạt |

Ngày 27/10/2026, bốn persisted binding Antigravity/OpenCode/Codex/Codex-Orca đều khởi chạy được server, thấy đủ mười bảy tool và liệt kê được tám marking asset `approved_for_insert` từ catalog `ATGT-ASSETS-20261026-V1`. Civil/port 8070 không chạy tại lần kiểm tra này nên chưa lặp thao tác ghi. Lần nghiệm thu trước đã đọc đúng khai báo `DO` = tim và `mepduong` = mép trên nguồn TÂY VẠN CANH; file nguồn không bị ghi, bản QA và manifest nằm dưới `outputs/cad/`.

Live QA trước đây đã ghi/đọc lại 4.4 đơn giản (khung kín + hai chéo), 3.1a có bulge cung cong và 3.1b. Survey live đọc 6.627 entity thành 94 nhóm layer/type; hai polyline `mepduong` được trả đúng vertex, bulge và chiều dài, còn `TIM TUYEN` được nhận đúng là `ACAD_PROXY_ENTITY` chưa thể offset native. Tool import linetype chỉ lấy `VACH_3.1B_0.6M` và kiểm tra dashes `+0,6/-0,6`. Importer block mới đã qua test và stdio nhưng chưa được nghiệm thu live; P.102 vẫn bị chặn vì chưa kiểm định scale/đơn vị và chưa xuất Book2 từ số liệu dự án thật.

Khảo sát nguồn ngày 26/10 dùng đúng layer do user khai báo, không dùng heuristic làm quyết định: `DO` có một LWPOLYLINE 54 đỉnh dài khoảng 9.078,725 m; `mepduong` có bốn LWPOLYLINE, gồm một nhánh ngắn và một tuyến ở vùng tọa độ khác. Vì vậy kết quả chỉ sẵn sàng cho bước đọc geometry; `topology_status` vẫn là `unverified` cho tới khi tách trái/phải, tuyến chính/nhánh và phạm vi thiết kế.
