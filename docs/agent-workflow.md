# Cách giao việc cho Orca và các agent

Đây là hợp đồng làm việc cho phần đã có, chưa phải tuyên bố đã cài một MCP ATGT mới hoặc đã thử luồng Orca → Antigravity → Civil.

## Thứ tự dùng dữ liệu

1. Khóa mã kiểm tra PDF, thư viện, template và phiên bản ảnh chụp dữ liệu dự án.
2. Tra điều/khoản và hình QCVN liên quan. Chỉ mục toàn văn phục vụ tìm nguồn; số liệu từ chú thích LIN và bản mẫu không có ưu tiên cao hơn QCVN.
3. Phân biệt quy định QCVN với thực hành người dùng, ví dụ offset 0,30/0,50 m và ngưỡng ghép nhánh 4.4 5/30 m.
4. Đọc bình đồ thành các khoảng có ngữ nghĩa: loại đường, mép nào, phía nào, chiều tuyến, nhánh/lối mở, phạm vi khoảng mở và quyết định cho phép chuyển hướng.
5. Gọi bộ lập phương án thuần dữ liệu. Đưa các khoảng bị chặn vào danh sách cần xử lý; không tự điền bằng chứng còn thiếu.
6. Thẩm tra phương án, dựng và kiểm tra hình học trong bản sao DWG, đọc lại từng đối tượng đã tạo; sau đó mới đo bóc và điền Excel.

## Phân công

| Vai trò | Đầu vào | Kết quả |
|---|---|---|
| Orca điều phối | Phạm vi công việc và bộ nguồn khóa phiên bản | Nhiệm vụ có phụ thuộc, trạng thái từng khoảng, một phiên ghi CAD |
| Agent tra cứu | Chỉ mục QCVN, câu hỏi theo mã/điều | Nguồn, trang, hình, điều kiện, ngoại lệ; không gọi lệnh ghi CAD |
| Agent đọc bình đồ | Bản sao DWG, tim và mép người dùng chỉ định | Hình học có handle/tim/chiều/đơn vị và căn cứ phân loại |
| Agent lập phương án | Các khoảng đã nhận diện và căn cứ tổ chức giao thông | Đề xuất 3.1a/3.1b hoặc nhóm ô 4.4 và các vấn đề chưa đủ dữ liệu |
| Agent kiểm tra | Phương án + nguồn + tài sản | Chấp nhận hoặc trả lại từng quyết định có lý do |
| Bộ ghi Civil | Phương án đã kiểm tra, đúng bản vẽ và snapshot | Đối tượng có mã sở hữu; trạng thái ghi/đọc lại, không xóa toàn layer |
| Agent thống kê | Đối tượng đã đọc lại + ledger | Bản sao Excel theo mẫu, loại cột biển do người dùng nhập |

Hiện các hàm Python, CLI và [MCP ATGT cục bộ](mcp-integration.md) có thể dùng để tra cứu/lập phương án. [Xuất Book2 từ ledger đã xác minh](book2-export.md) đã thử với dữ liệu giả định trong Excel thật. Bộ đọc ngữ nghĩa bình đồ và bộ ghi Civil là các bước triển khai tiếp; không mô tả chúng là đã chạy. Agent thống kê chỉ nhận ledger từ bước đọc lại/đo bóc, không tự đặt `verified` cho một phương án thiết kế.

## Thông tin không được tự suy ra

- Loại đường chỉ từ số làn hoặc tên layer; dải phân cách vật lý khác vạch tim sơn.
- Quyền rẽ/chuyển hướng chỉ từ việc có một đường nhánh hoặc nét đứt.
- Phạm vi 4.4 chỉ từ sự hiện diện của 3.1b.
- Bề rộng thực từ mô tả trong file LIN; cỡ biển thực từ kích thước ký hiệu trên bình đồ.
- Lý trình từ khoảng cách hình học khi có gốc tuyến, station equation hoặc nhiều tim tham chiếu.
- Số lượng dự án mới từ số liệu đã có trong Book2.xlsx.

## Khi tích hợp Civil ở lượt tiếp theo

Không cố định cổng 8080 theo skill cũ. Khai báo endpoint theo phiên và xác nhận `Document.Name` cùng định danh snapshot trước thao tác. Cổng 8050 trong trao đổi trước chưa chứng minh phiên hiện tại đang mở đúng DWG.

Giữ một bộ ghi theo thứ tự; các agent còn lại làm việc trên bản đọc/snapshot. Mỗi nhóm thao tác có mã lần chạy và mã đối tượng ổn định. Khi timeout, kiểm tra thao tác đã thực sự kết thúc trước khi tiếp tục; không gửi lặp lệnh tạo đối tượng. Nghiệm thu trên bản sao, có kiểm tra trực quan và đọc lại trước khi xuất khối lượng.
