# Quy tắc vị trí biển và cụm W.205/W.207

Trạng thái: bộ lập **đề xuất**, không tự cấp quyền ghi CAD. Phạm vi hiện tại là đường ô tô thông thường và đường đôi ngoài đô thị.

> Tài liệu này là bản giải thích/audit cho con người. Agent phải nạp quy tắc dự án từ `D:\DOCUMENT\TCVN\TIEU CHUAN TK ATGT\ATGT_PROJECT_RULES.toml` qua `atgt_get_project_rules`; không lấy nội dung lặp trong tài liệu này làm một nguồn quy tắc thứ hai.

## 1. Thứ tự ưu tiên nguồn

1. Tra đúng biển trong QCVN 41:2024/BGTVT. Nếu QCVN quy định vị trí hoặc khoảng cách cụ thể, dùng quy định đó và lưu trang/điều làm bằng chứng.
2. Chỉ khi đã ghi nhận rằng QCVN không có khoảng cách số áp dụng cho biển đó mới dùng tầm nhìn hãm xe tối thiểu `S1` theo TCVN 4054:2005, 5.1.1, Bảng 10.
3. Không thay tốc độ thiết kế bằng tốc độ khai thác, tốc độ hạn chế hoặc tốc độ đo được. Các tốc độ hợp lệ của Bảng 10 và `S1` tương ứng là: `20→20 m`, `30→30 m`, `40→40 m`, `60→75 m`, `80→100 m`, `100→150 m`, `120→210 m`.
4. Khoảng cách chỉ tạo vị trí ứng viên. Trước khi ghi CAD vẫn phải kiểm tra tầm nhìn thực tế theo chiều xe chạy, chướng ngại, phạm vi nền/lề, hình học station và tài sản biển.

Nguồn TCVN cục bộ được khóa bằng SHA-256 `B3DDCC3424DEC93E9BC2B83BA0D3DC9D42F472BDCF4149E6FF6C8DDE0A5359F1`. Nếu server chưa được cấu hình đúng nguồn này, mọi đề xuất dùng `S1` bị chặn.

## 2. W.205 và W.207 tại một nút

- `W.205a` đến `W.205e`: nút giao cùng mức của các tuyến cùng cấp, không có đường ưu tiên; căn cứ QCVN Phụ lục C.5, trang PDF 100.
- `W.207a` đến `W.207i`, `W.207k`, `W.207l`: đường ưu tiên giao với đường không ưu tiên; căn cứ QCVN Phụ lục C.7, trang PDF 100-101.
- Quan hệ ưu tiên phải có bằng chứng tổ chức giao thông; không suy ra chỉ từ kích thước nhánh hoặc hình học bình đồ.
- Biến thể phải khớp hình dạng nút và chiều xe chạy. Mọi nút lưu `priority_relationship`, `branch_side`, `geometry_evidence` và `priority_evidence`.

## 3. Gom các đường ngang liên tiếp

Các nút được sắp theo chiều xe chạy. Hai nút liên tiếp chỉ thuộc cùng cụm khi khoảng cách station nhỏ hơn `S1`; bằng đúng `S1` thì tách thành hai cảnh báo. Biển đại diện được đặt trước nút đầu của cụm một khoảng `S1`.

- Nếu cụm chỉ gồm các đường không ưu tiên: QCVN C.7(d) được ưu tiên. Dùng `W.207d` hoặc `W.207e` theo phía của nhánh gần vị trí đặt biển nhất; trong phạm vi đó không đặt thêm W.207 khác.
- Nếu cụm gần nhất là nút cùng cấp hoặc cụm trộn quan hệ ưu tiên: giữ họ/mã W.205 hoặc W.207 của nút đầu tiên gặp theo chiều xe chạy. Đây là thực hành dự án do người dùng phê duyệt (`USER-SIGN-20261026-v1`), không trích dẫn thành yêu cầu QCVN.
- Với cụm nhiều nút, gắn `S.501`. Chiều dài theo quy tắc người dùng là khoảng cách dọc tuyến từ vị trí biển đại diện đến nút cuối cụm. Giá trị mét được làm tròn đến hàng chục theo QCVN Phụ lục F.1, trang PDF 151.

QCVN dùng khái niệm "mật độ lớn" nhưng không cho ngưỡng số. Điều kiện `< S1` là quy tắc dự án để agent nhận diện ứng viên gom cụm; kết quả vẫn cần thẩm tra độc lập trước khi ghi CAD.

## 4. Điều kiện chặn

Đề xuất bị chặn nếu thiếu một trong các dữ liệu sau: snapshot; tim và phạm vi station; chiều xe chạy; tốc độ thiết kế đúng Bảng 10; bằng chứng đã tra QCVN; quan hệ ưu tiên; bằng chứng hình học/biến thể; nguồn TCVN đúng hash; hoặc vị trí tính ra nằm ngoài phạm vi Alignment.

Đầu ra luôn có `cad_execution_allowed=false`. Sau khi `atgt_validate_plan` tính lại khớp, agent vẫn phải qua geometry review, asset review, independent design review, tạo work copy, ghi có `run_id` và đọc lại trước khi lưu.
