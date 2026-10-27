# MCP tra cứu và lập đề xuất ATGT

Phạm vi tiếp nối được người dùng yêu cầu: tiếp tục hệ thống hiện tại, tận dụng skill 4.4, giữ phần đọc ghi chú CAD sang lượt sau. Tiêu chí của lát triển khai này là agent gọi được nguồn và quy tắc hiện có qua giao thức MCP thật, có thông báo thiếu căn cứ, không phát sinh quyền ghi bản vẽ.

Ba phương án: chỉ giữ CLI (ít phụ thuộc nhưng agent phải tự quản lý file), MCP stdio dùng chung lõi Python (phù hợp host trên máy hiện tại), hoặc HTTP độc lập (thêm cổng/lifecycle/xác thực chưa cần). Chọn stdio; không thay lõi đã kiểm thử hoặc thêm bộ suy luận cạnh tranh.

`service.py` giữ hợp đồng đọc nguồn và tính đề xuất; `mcp_server.py` cung cấp schema, kiểm tra kiểu/lô. Thiết kế ban đầu đăng ký sáu công cụ; từ 26/10/2026 có thêm `atgt_get_project_rules`, thành bảy công cụ. SQLite mở read-only. Metadata khóa PDF được ghi trong bước ingest; server kiểm tra hash DB/LIN/ruleset mỗi lần gọi và dừng khi nguồn đổi giữa phiên. Cấu hình file chỉ nằm ở đối số khởi động. Kết quả có nguồn, trạng thái đề xuất và quyền CAD luôn false.

Kiểm tra ở hai ranh giới: test subprocess stdio với DB/LIN giả định để kiểm tra lỗi và nguồn thay đổi; probe riêng trên chỉ mục thật và các tình huống hình học giả định. Cuối cùng kiểm tra trong host Orca/Antigravity riêng; không suy ra từ SDK client. Tiếp tục giữ nguồn và báo cáo chi tiết ngoài Git, chỉ công bố code, schema, tài liệu và ví dụ giả định.
