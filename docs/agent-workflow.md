# Cách giao việc cho Orca và các agent

Đây là hợp đồng làm việc cho hai MCP đã có: `atgt` đọc nguồn/lập đề xuất và `atgt-cad` ghi có kiểm soát trên bản sao. Luồng cấu hình thật đã được thử qua Antigravity, Codex, Codex runtime của Orca và OpenCode; nghiệm thu live bao phủ cụm ghi chú biển cùng mẫu 3.1a/3.1b/4.4, nhưng chưa phải thiết kế toàn tuyến.

Skill `thiet-ke-atgt-qcvn41` đóng gói thứ tự gọi cho agent và đã được Orca phát hiện từ Agent skills home. Skill không chứa bản sao các con số quy tắc: nó buộc agent nạp file ruleset đã cấu hình qua MCP. Skill không thay quyền của MCP và không biến proposal thành phê duyệt ghi CAD.

## Nạp knowledge xuyên suốt

Mỗi task phải gọi `atgt_status`, sau đó `atgt_get_project_rules(section="all")`, rồi giữ `ruleset_id` và `project_rules_sha256` trong toàn bộ proposal/validation của task. Ruleset máy đọc duy nhất hiện đặt tại `D:\DOCUMENT\TCVN\TIEU CHUAN TK ATGT\ATGT_PROJECT_RULES.toml`, cạnh QCVN. Nếu file thay đổi giữa phiên, MCP từ chối tiếp tục và yêu cầu khởi động lại sau khi review/version hóa.

Prompt người dùng chỉ cần khai báo dữ liệu riêng của dự án: DWG đang mở, layer tim/mép, loại/cấp đường, tốc độ thiết kế, gốc/chiều lý trình, station equation và các ngoại lệ quan hệ ưu tiên. Không chép lại các quy tắc dùng chung đã có trong ruleset.

## Thứ tự dùng dữ liệu

1. Khóa mã kiểm tra PDF, LIN, TCVN 4054, ruleset, catalog tài sản, thư viện/template và phiên bản ảnh chụp dữ liệu dự án.
2. Tra điều/khoản và hình QCVN liên quan. Chỉ mục toàn văn phục vụ tìm nguồn; số liệu từ chú thích LIN và bản mẫu không có ưu tiên cao hơn QCVN. Với vị trí biển, dùng khoảng cách/vị trí QCVN nếu có; chỉ sau khi xác nhận QCVN không có khoảng cách số mới dùng S1 theo TCVN 4054:2005 Bảng 10.
3. Phân biệt quy định QCVN với thực hành người dùng, ví dụ offset 0,30/0,50 m và ngưỡng ghép nhánh 4.4 5/30 m.
4. Nhận layer tim và layer mép do user khai báo cho đúng bản vẽ/snapshot; không mang tên layer từ dự án trước sang dự án sau. Đọc bình đồ thành các khoảng có ngữ nghĩa: loại đường, mép nào, phía nào, chiều tuyến, nhánh/lối mở, phạm vi khoảng mở và quyết định cho phép chuyển hướng.
5. Gọi bộ lập phương án thuần dữ liệu. Đưa các khoảng bị chặn vào danh sách cần xử lý; không tự điền bằng chứng còn thiếu.
6. Với block, tra catalog bằng mã, chỉ chọn `asset_id` đã duyệt, import vào bản sao và đọc lại block-table trước khi đặt. Agent không truyền đường dẫn DWG hoặc tên block đoán tay.
7. Thẩm tra phương án, dựng và kiểm tra hình học trong bản sao DWG, đọc lại từng đối tượng đã tạo; sau đó mới đo bóc và điền Excel.

## Phân công

| Vai trò | Đầu vào | Kết quả |
|---|---|---|
| Orca điều phối | Phạm vi công việc và bộ nguồn khóa phiên bản | Nhiệm vụ có phụ thuộc, trạng thái từng khoảng, một phiên ghi CAD |
| Agent tra cứu | Chỉ mục QCVN, câu hỏi theo mã/điều | Nguồn, trang, hình, điều kiện, ngoại lệ; không gọi lệnh ghi CAD |
| Agent đọc bình đồ | Bản sao DWG, tim và mép người dùng chỉ định | Hình học có handle/tim/chiều/đơn vị và căn cứ phân loại |
| Agent lập phương án | Các khoảng đã nhận diện và căn cứ tổ chức giao thông | Đề xuất vị trí biển, W.205/W.207/S.501, 3.1a/3.1b hoặc nhóm ô 4.4 và các vấn đề chưa đủ dữ liệu |
| Agent kiểm tra | Phương án + nguồn + tài sản | Chấp nhận hoặc trả lại từng quyết định có lý do |
| Bộ ghi Civil | Phương án đã kiểm tra, đúng bản vẽ và snapshot | Đối tượng có mã sở hữu; trạng thái ghi/đọc lại, không xóa toàn layer |
| Agent thống kê | Đối tượng đã đọc lại + ledger | Bản sao Excel theo mẫu, loại cột biển do người dùng nhập |

Hiện các hàm Python, CLI và [MCP ATGT cục bộ](mcp-integration.md) có thể tra cứu/lập phương án. `atgt-cad` đã tạo bản sao từ trạng thái Civil đang mở, đồng bộ đơn vị, đặt và đọc lại một cụm block+leader+lý trình cùng các mẫu 3.1a, 3.1b và 4.4 đơn giản, rồi lưu bản QA riêng. Bộ ghi mới có catalog khóa hash, import block theo `asset_id`, biên nhận block-table và lệnh đặt block vạch 7.6/9.3; tám block trong template đã qua kiểm tra cấu trúc, còn chèn live phải nghiệm thu khi Civil/8070 mở đúng nguồn. Lớp survey nhận layer tim/mép do user khai báo theo snapshot, kiểm kê layer/type và đọc geometry native theo handle; role hint tự động chỉ là công cụ tìm kiếm dự phòng. [Xuất Book2 từ ledger đã xác minh](book2-export.md) đã thử với dữ liệu giả định trong Excel thật. Việc tự xác nhận topology trái/phải/tuyến chính/nhánh, chuyển quyết định sang hình học hàng loạt và ledger dự án thật vẫn là các bước tiếp theo; agent thống kê không tự đặt `verified`.

## Thông tin không được tự suy ra

- Loại đường chỉ từ số làn hoặc tên layer; dải phân cách vật lý khác vạch tim sơn.
- Quyền rẽ/chuyển hướng chỉ từ việc có một đường nhánh hoặc nét đứt.
- Phạm vi 4.4 chỉ từ sự hiện diện của 3.1b.
- Bề rộng thực từ mô tả trong file LIN; cỡ biển thực từ kích thước ký hiệu trên bình đồ.
- Lý trình từ khoảng cách hình học khi có gốc tuyến, station equation hoặc nhiều tim tham chiếu.
- Số lượng dự án mới từ số liệu đã có trong Book2.xlsx.
- Tên layer tim/mép từ bản mẫu hoặc dự án trước; user phải khai báo lại theo từng bản vẽ.
- Tốc độ thiết kế từ biển hạn chế tốc độ hoặc vận tốc quan sát; quan hệ ưu tiên từ bề rộng nhánh; tầm nhìn thực tế thông thoáng chỉ từ giá trị S1 tối thiểu.

## Hợp đồng Civil hiện hành

Endpoint là cấu hình khởi động; phiên hiện tại đã thử ở `127.0.0.1:8070`. Luôn xác nhận `Document.Name`, đường dẫn đầy đủ, `INSUNITS` và snapshot trước thao tác; không suy ra từ caption cửa sổ.

Giữ một bộ ghi theo thứ tự; các agent còn lại làm việc trên bản đọc/snapshot. Mỗi nhóm thao tác có mã lần chạy và mã đối tượng ổn định. Khi timeout, kiểm tra thao tác đã thực sự kết thúc trước khi tiếp tục; không gửi lặp lệnh tạo đối tượng. Nghiệm thu trên bản sao, có kiểm tra trực quan và đọc lại trước khi xuất khối lượng.
