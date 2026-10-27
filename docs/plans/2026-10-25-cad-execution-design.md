# Thiết kế tầng thực thi ATGT CAD — 25/10/2026

## Quyết định kiến trúc

Giữ hai MCP độc lập. `atgt` chỉ đọc QCVN, tài sản và tính đề xuất; `atgt-cad` là bộ ghi có phạm vi hẹp. Một agent có thể gọi cả hai nên trải nghiệm vẫn là “giao cho agent”, nhưng lỗi prompt/tra cứu không tự biến thành quyền ghi tùy ý.

`atgt-cad` nhận nguồn, thư mục đầu ra, host và cổng ở lúc khởi động. Tool không nhận đường dẫn file. Mỗi phiên tạo một thư mục và DWG mới từ `Database.Wblock()` của trạng thái đang mở; vì vậy bắt được cả thay đổi chưa lưu mà không lưu file nguồn. Nguồn prototype duy nhất là `BD TK ATGT TAY VAN CANH.dwg`.

## Chuỗi an toàn

1. Đọc health, đường dẫn đầy đủ, DBMOD, INSUNITS, extents và số đối tượng.
2. Tạo bản làm việc mới; tên phiên chỉ gồm ký tự an toàn và không được dùng lại.
3. Mở bản sao. Wblock của mẫu thực tế mở lại với INSUNITS Feet dù nguồn là Meters, nên có bước đồng bộ đơn vị trên bản sao và đọc lại trước mọi batch.
4. Mỗi run có plan ghi trước và `run_id` dùng một lần. Lô tối đa 50 hành động.
5. Chỉ ghi bản sao đang active. Mỗi entity mang XData `ATGT_AGENT/run/action/kind/code`.
6. Đọc ngược độc lập. Với cụm biển phải đủ DBText, Leader và BlockReference; đối chiếu nội dung, layer, block, tọa độ, rotation, scale và quan hệ hình học.
7. Chỉ run đạt read-back mới được đưa vào manifest và cho phép lưu bản sao.
8. Ledger/Book2 chỉ nhận đối tượng đã đo bóc từ snapshot đọc lại, không nhận trực tiếp proposal.

## Archetype ghi chú biển đã xác minh

Mẫu chuẩn `km7+409`/`207a_245a`: DBText layer `BIEN-BAO`, style ARIALH, cao 2,0; Leader 3 đỉnh, dimstyle `duonggiao`; block nằm tại đỉnh cuối. Archetype được tìm bằng thuộc tính và khoảng cách, không dùng handle vì handle đổi sau Wblock. Các biến thể I.439, 2 đỉnh, ISO-25 và nền vàng vẫn bị loại khỏi đường tự động chuẩn.

## Trạng thái nghiệm thu

Phiên `tayvancanh-qa-20261025-02` đã tạo từ nguồn có DBMOD 21, đồng bộ về Meters, đặt một cụm biển QA, một vạch 4.4 đơn giản, một vạch 3.1a có bulge cung cong và một vạch 3.1b ngoài extents dự án. Linetype 3.1b được nhập từ template và xác minh `+0,6/-0,6`; các run đều đọc lại không có lỗi hình học rồi lưu riêng. Hash DWG sau lưu cuối: `1db2c824d2879a9465c4fe374b49c8c38c096f35c9e3056497ec3f4795a1043d`.

Bốn cấu hình persisted đều khởi chạy được server và gọi `atgt_cad_status` + `atgt_cad_verify_run`. Native Codex/Orca và Antigravity nhận cấu hình; `opencode mcp list` toàn cục timeout 30 giây nên không lặp, nhưng chính binding OpenCode đã bắt tay/call tool thành công qua SDK.

Lớp survey chỉ đọc đã được bổ sung và thử live: 6.627 entity được gom thành 94 nhóm layer/type; tool geometry trả exact vertex/bulge/width cho LWPOLYLINE và biểu diễn native cho Line/Arc/Circle. Mỗi lần tối đa 50 handle, 20.000 vertex/entity và 50.000 vertex tổng; vượt giới hạn thì dừng, không cắt dữ liệu. Role hint theo tên layer luôn mang trạng thái `unverified`. Trong mẫu, hai polyline `mepduong` đọc được chính xác nhưng `TIM TUYEN` là `ACAD_PROXY_ENTITY`, không được coi là Alignment/Curve để offset. Thử `Explode` proxy chỉ trong bộ nhớ trả 892 LWPOLYLINE ngắn và 880 CIRCLE trên layer `VANG`, không phải một tim liên tục; thao tác không ghi DWG.

Chưa coi hệ thống hoàn tất toàn tuyến: writer yêu cầu vertex+bulge native đã xác minh nhưng chưa tự offset từ Curve/Alignment, chưa xác nhận vai trò layer/topology và chưa xử lý tim proxy. Ngoài ra còn kiểm định tài sản biển đầy đủ, đo bóc thật và kiểm tra trực quan Civil ở vùng QA (cửa sổ Civil đang minimized khi thử chụp).

## Bổ sung hợp đồng layer do user khai báo — 26/10/2026

Không hard-code `DO` hoặc `mepduong` thành quy ước toàn hệ thống và không dùng heuristic tên layer làm quyết định. Mỗi dự án phải truyền `snapshot_id`, `centerline_layers` và `road_edge_layers` vào `atgt_cad_survey_declared_layers`. Tool so khớp tên exact không phân biệt hoa/thường, cấm cùng layer mang hai vai trò, báo layer thiếu/rỗng, phân trang tối đa 200 entity và giữ `topology_status=unverified`.

Nghiệm thu live trên nguồn TÂY VẠN CANH: `DO` có một LWPOLYLINE 54 đỉnh dài 9.078,725 m; `mepduong` có bốn LWPOLYLINE dài lần lượt khoảng 86,216 m, 8.917,346 m, 8.974,240 m và 8.974,240 m. Một mép nằm ở vùng tọa độ khác, nên việc khai báo layer mới chỉ xác nhận vai trò của layer chứ chưa tự xác nhận entity nào là mép trái/phải của đúng tuyến.
