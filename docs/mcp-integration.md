# MCP ATGT cục bộ — 25/10/2026

## Phạm vi đã triển khai

MCP chạy qua `stdio`, dùng SDK Python và các hàm đã có trong repo. Đây là bộ công cụ đọc nguồn/lập đề xuất, chưa phải bộ điều khiển Civil. Không cung cấp lệnh ghi CAD, tự duyệt rule, đọc file tùy ý, chạy shell hay sửa SQLite qua lời gọi công cụ.

Chọn `stdio` cho máy hiện tại vì host khởi chạy tiến trình trực tiếp, không phải giữ một cổng HTTP mới hoặc một dịch vụ mạng. Có thể mở nhiều phiên đọc cùng bộ nguồn. Phần ghi Civil sau này vẫn cần một bộ ghi duy nhất theo bản vẽ. SDK được giới hạn `mcp>=1.28.1,<2`, tránh đổi API lớn ngoài dự kiến. Tham khảo [SDK chính thức v1.28.1](https://github.com/modelcontextprotocol/python-sdk/tree/v1.28.1) và [quy định stdio](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).

| Công cụ | Nhiệm vụ | Giới hạn kết quả |
|---|---|---|
| `atgt_status` | Mã nguồn, số trang/tài sản, phạm vi triển khai | Phân biệt sẵn sàng đọc với CAD đã nghiệm thu |
| `atgt_search` | Tìm cụm từ/mã trong QCVN | Mặc định 5, tối đa 20 kết quả; có phân trang |
| `atgt_get` | Lấy trang PDF, chỉ mục biển hoặc vạch | Văn bản từng cửa sổ tối đa 6.000 ký tự |
| `atgt_resolve_asset` | Tìm DWG ứng viên theo mã đầy đủ | Không biến gợi ý từ tên file thành block đã duyệt |
| `atgt_evaluate_rules` | Đề xuất 3.1a/3.1b hoặc 4.4 đơn giản | Tối đa 50 khoảng hoặc 10 nhóm nút; cùng một snapshot |
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

Chỉ mục cũ phải dựng lại bằng `atgt.qcvn_ingest` để có metadata khóa PDF. Nếu thiếu metadata, server dừng với hướng dẫn dựng lại; không tự sửa DB khi khởi động. Đường dẫn SQLite và LIN là cấu hình khi khởi động, không phải tham số để agent trỏ tới file bất kỳ.

```powershell
.\.venv\Scripts\python.exe -m atgt.mcp_server `
  --db 'D:\AGENT_AI\ATGT-Design-Automation\local-manifests\knowledge\atgt-knowledge.sqlite' `
  --lin 'E:\TEMPLATE CV\BINH DO ATGT DU AN MAU\VACH_SON_QCVN41_2024.lin'
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

Client SDK đã khởi chạy server từ từng bản cấu hình thực tế, ở thư mục ngoài repo và không thêm `PYTHONPATH`: cả bốn đường cấu hình nhận đủ sáu công cụ, gọi được `atgt_status` và tìm `P.102`, cùng trả về 403 trang, 84 điều, 338 tài sản và 14 mẫu nét. Kiểm tra OpenCode chỉ bật ATGT trong tiến trình chẩn đoán bằng cấu hình tạm thời; các MCP khác trong file cấu hình vẫn giữ nguyên.

Phép kiểm tra Codex app-server dùng runtime Orca hết thời gian sau 30 giây; nhật ký đồng thời ghi lỗi 401 ở các yêu cầu tài khoản/plugin/model. Đã dừng tiến trình kiểm tra và không thay đăng nhập. Chưa chứng minh đây là nguyên nhân của timeout, cũng chưa coi đó là lỗi ATGT. Orca đang đóng khi kiểm tra; chưa có nghiệm thu phiên agent trong UI. Không có lượt gọi model hay thao tác Civil nào trong đợt gắn cấu hình này.

Khi mở lại Orca, mở phiên agent mới tại repo này để nhận cấu hình. Nhiệm vụ đầu tiên có thể dùng:

> Dùng MCP atgt gọi atgt_status, tìm P.102 và lấy căn cứ vạch 3.1a/3.1b. Báo rõ nguồn và phần còn thiếu dữ liệu; chưa thực thi CAD.

Bằng chứng và đường dẫn bản sao lưu được giữ cục bộ trong `local-manifests/mcp/deployment.json`, `client-bindings-evidence.json` và `native-host-evidence.json`; không đưa cấu hình tài khoản lên Git.

## Luồng gọi cho agent

1. `atgt_status`: giữ mã nguồn và kiểm tra đúng phạm vi.
2. `atgt_search` rồi `atgt_get`: lấy căn cứ theo mã/điều/trang. Khi có phân trang, dùng `next_offset` để lấy phần còn lại.
3. `atgt_resolve_asset`: xác định ứng viên và các kiểm tra hình học còn thiếu.
4. Sau khi đo bình đồ, gọi `atgt_evaluate_rules` với ngữ cảnh có snapshot, tim, mép, loại đường và bằng chứng chuyển hướng/không dừng.
5. Gửi cả ngữ cảnh gốc và kết quả nhận được vào `atgt_validate_plan`. `ready_for_geometry_review=true` nghĩa là đề xuất nhất quán, vẫn cần thẩm tra hình học và CAD.
6. Sau bước ghi/đọc lại Civil trong tương lai, đưa ledger đã đo sang bộ xuất Book2. MCP hiện tại không tạo khối lượng từ đề xuất.

## Đã kiểm tra

```powershell
.\.venv\Scripts\python.exe scripts/check_mcp.py `
  --db local-manifests/knowledge/atgt-knowledge.sqlite `
  --lin 'E:\TEMPLATE CV\BINH DO ATGT DU AN MAU\VACH_SON_QCVN41_2024.lin' `
  --output local-manifests/mcp/live-probe.json
```

Đã khởi chạy subprocess MCP thật, bắt tay, liệt kê và gọi cả sáu công cụ trên bộ nguồn thật: 403 trang, 84 điều, 338 tài sản, 14 mẫu nét. Đề xuất hình học dùng dữ liệu giả định: ba khoảng vạch mép, một khoảng thiếu căn cứ bị chặn; một nhóm ngã tư tạo một ô 4.4. P.102 trả về đúng ứng viên `Bien_Cam/102.dwg`, trạng thái vẫn chưa xác minh.

Toàn repo đạt 100 kiểm thử trong môi trường riêng; MCP SDK thực tế 1.30.0, Pydantic 2.14.1. Đã sửa lỗi tokenizer bỏ sót tìm không dấu `bien cam`/`mat vong` khi nguồn là `biển cấm`/`mắt võng`; vẫn ưu tiên mã đầy đủ hoặc từ khóa có dấu (đ/ d chưa được đồng nhất). Một cảnh báo chuyển đổi API `fitz` từ PyMuPDF 2.0 không làm hỏng phép kiểm tra; chưa coi cảnh báo đó là lỗi của dữ liệu QCVN.

Kiểm tra qua giao thức trên fixture độc lập: phân trang không trùng, lấy cửa sổ văn bản, không nhận đường dẫn thay số trang, không nhận FTS/SQL từ người gọi, từ chối xác minh kiểu chuỗi, lô quá lớn, trộn snapshot, phương án bị thay và nguồn bị sửa giữa phiên. Các lời gọi đọc giữ nguyên byte DB.

Đây là nghiệm thu giao thức MCP và quy tắc trên dữ liệu giả định. Kiểm tra trong UI Orca/Antigravity và chạy trên bản sao Civil vẫn phải ghi nhận riêng. Bộ câu hỏi `evals/mcp-atgt.xml` dành cho đánh giá agent; chưa tuyên bố đã chạy một đợt đánh giá LLM độc lập.
