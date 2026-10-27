# Hợp đồng layer tim/mép do user khai báo — 26/10/2026

## Quyết định

Mỗi bản vẽ có thể dùng tên layer khác nhau. User hoặc tác vụ đầu vào phải khai báo danh sách layer tim và danh sách layer mép cùng `snapshot_id` vừa lấy từ Civil. `DO` và `mepduong` chỉ là dữ liệu của bản TÂY VẠN CANH, không phải mặc định toàn cục.

Không chọn phương án hard-code tên layer vì sẽ sai ngay ở dự án kế tiếp. Không chọn phương án chỉ đoán theo từ khóa vì layer `TIM TUYEN` trong mẫu từng là proxy gây hiểu nhầm. Phương án được chọn là một tool read-only riêng: `atgt_cad_survey_declared_layers`.

## Dòng dữ liệu

1. Gọi `atgt_cad_status`, lấy đường dẫn đầy đủ, đơn vị và `snapshot_id`.
2. Truyền `centerline_layers` và `road_edge_layers` do user khai báo.
3. Tool kiểm tra snapshot còn đúng, layer tồn tại, không rỗng và không xung đột vai trò.
4. Tool trả entity khớp theo trang, gồm role, layer, handle, loại, chế độ geometry, chiều dài, số vertex và extents.
5. Agent chọn handle liên quan rồi gọi `atgt_cad_extract_native_geometry` theo batch tối đa 50.
6. Việc phân loại mép trái/phải, tuyến chính/nhánh, dải phân cách và phạm vi thiết kế là gate topology riêng; không suy ra chỉ từ layer.

## Lỗi và giới hạn

- Snapshot đổi: dừng và yêu cầu khảo sát lại.
- Layer thiếu/rỗng: `ready_for_geometry_extraction=false`.
- Một layer được khai báo cho cả tim và mép: từ chối trước khi gọi Civil.
- Entity proxy hoặc non-curve: trả trạng thái không hỗ trợ, không xấp xỉ chord.
- Kết quả phân trang 1–200 entity; không trả toàn bộ model space không giới hạn.

## Tiêu chí nghiệm thu

- `DO` được nhận là tim dù heuristic tên layer không nhận ra.
- `mepduong` được nhận là mép theo đúng user input.
- Kết quả khóa với đúng source snapshot và không ghi DWG.
- Cả Antigravity, OpenCode, Codex và Codex-Orca thấy/call được tool từ cấu hình persisted.
- Kiểm thử owner-boundary bảo vệ snapshot, xung đột vai trò và kết quả topology chưa xác minh.
