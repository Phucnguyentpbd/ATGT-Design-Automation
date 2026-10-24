# Rà soát repo và triển khai tiếp — 24/10/2026

Điểm bắt đầu: commit `73009f02b1e06c34168803f2fec349f55e65b765` của `Phucnguyentpbd/ATGT-Design-Automation`.

**Kết luận:** cấu trúc nguồn → tri thức → quy tắc → phương án → CAD → khối lượng là hợp lý. Repo ban đầu là nền tảng Python, chưa có thiết kế tự động toàn tuyến. Tên báo cáo “knowledge completion” chỉ thể hiện đã lập chỉ mục nguồn, không chứng minh agent ra quyết định hoặc vẽ đúng.

## Lỗi đã xác nhận và sửa

| Phát hiện | Hậu quả | Cách sửa / bằng chứng |
|---|---|---|
| Hàm chia khối lượng không kiểm tra khoảng sơn chồng/ngoài biên như hàm tổng | Tổng và bảng theo đoạn có thể không nhất quán | Dùng chung kiểm tra khoảng và bề rộng; bốn đầu vào lỗi đã tái hiện trước sửa |
| Có thể tổng hợp lặp cùng một `face_id` | Đếm tăng số mặt biển | Kiểm tra danh sách mặt biển trước tổng hợp; thử lặp cùng mặt biển bị từ chối |
| Kiểm tra mã biển nhận `XYZ.102`, `P.foo`, `P.102.`, `P.102-103` | Mã không đúng cấu trúc lọt vào dữ liệu | Giới hạn nhóm tiền tố/cấu trúc và giữ mã đặc thù; kiểm tra cú pháp không thay kiểm định mã thực |
| Nhiều phiên bản approved của một rule cùng được trả về | Có thể áp dụng hai bộ thông số trái nhau | Chỉ chọn phiên bản approved mới nhất, rồi xét phạm vi đường; draft mới không che approved hiện hành |
| Dựng lại chỉ mục xóa DB cũ trước khi hoàn tất | Một lỗi LIN/catalog làm mất chỉ mục đang dùng | Dựng trong thư mục tạm, đóng kết nối, chỉ công bố DB hoàn chỉnh sau khi kiểm tra thành công |
| Importer chỉ chấp nhận catalog gắn với Library.rar, không nhận đầu ra scanner của repo | Quét thư viện tại máy xong vẫn không dựng knowledge được | Nhận bản kê native hoặc wrapper `sign_assets`; kiểm tra ID/đường dẫn/mã kiểm tra, không tự nâng trạng thái duyệt |
| Có hai bộ phân tích LIN với kiểm tra không đồng nhất | Ingestion và inventory có thể hiểu tài sản khác nhau | Dùng chung `parse_lin`, giữ các đoạn nét dạng số thập phân |

Mười hai ca hồi quy thuộc sáu nhóm đầu đã thất bại trên đường xử lý trước sửa, sau đó đạt. Bộ kiểm tra sẵn có ban đầu: **44 đạt**. Sau bổ sung kiểm tra quy tắc và tích hợp skill: **82 đạt**, không bỏ qua ca kiểm tra nào. PyMuPDF có cảnh báo deprecation của binding SWIG; không có lỗi kiểm tra.

## Phần đã bổ sung

- `edge_rules.py`: đề xuất 3.1a/3.1b theo khoảng có dữ liệu, offset tim 0,30/0,50 m từ người dùng, điều kiện QCVN trang 166–167, phạm vi lối mở và quyền chuyển hướng có căn cứ.
- `skill44_classifier.py`: tái sử dụng hàm phân loại của skill vạch 4.4, giữ lịch sử nguồn bằng SHA-256.
- `box44_rules.py`: kiểm tra trước khi gọi classifier; không nâng bề rộng lên 3,7 m, không ghép mơ hồ, không áp ô chung vượt dải phân cách, không gọi bộ xóa/vẽ của script cũ.
- `planning_cli.py` và ví dụ giả định: tạo phương án JSON có căn cứ, vấn đề và các kiểm tra còn thiếu. Không gửi lệnh CAD.
- Tài liệu quy tắc, hợp đồng agent, chỉ dẫn dự án và thống nhất tên/hash Book2.xlsx.

## Nguồn đã kiểm tra lại tại máy

| Nguồn | Kết quả |
|---|---|
| QCVN_41_2024_mo_khoa.pdf | SHA `84825a72…dbbd46`, 403 trang, đúng khóa |
| Book2.xlsx hiện tại | SHA `19672f2b…985`, 2.070.212 byte, đúng khóa hiện hành trong script; sửa tên/hash cũ còn sót trong tài liệu |
| TEMPLATE_VACH_SON_ATGT_QCVN41_2024.dwg | SHA `62662e91…e16080`, 481.632 byte, header AC1021; chưa xác minh hình học/đơn vị |
| VACH_SON_QCVN41_2024.lin | SHA `e4484f09…15c99`, 1.633 byte, 14 kiểu nét; không lấy chú thích làm thông số đã duyệt |
| Thư viện biển AtgtPro | 338 DWG, tổng 69.791.520 byte, nhóm 69/122/33/83/31 khớp bảng khóa |

Dựng lại knowledge từ các file thật thành công: 84 điều, 13 phụ lục, 412 neo điều khoản, 502 mã biển được nhắc trong văn bản, 50 mã vạch được nhận diện, 338 tài sản và 14 kiểu nét. Gợi ý mã từ tên file trong lần quét này: 320 đơn ứng viên, 8 nhiều ứng viên, 10 chưa khớp; các số này thay thế việc áp số liệu catalog lịch sử cho thư viện hiện tại. **Không có tài sản hình học hoặc quy tắc CAD nào được tự động đánh dấu approved.**

PDF trang 166–167 và 177–178 đã được đọc; các trang hình 167/178 đã được dựng ảnh và đối chiếu. Các trang khác trong chỉ mục vẫn cần thẩm tra theo từng quyết định. Danh sách tám trang ít văn bản không có nghĩa chỉ tám trang cần kiểm tra hình/bảng.

Book2.xlsx còn 384 phần liên kết ngoài, 4.484 defined names và tám ô lưu lỗi #REF!. Đây là hiện trạng file nguồn; chưa sửa nguồn và chưa tạo bảng thống kê dự án mới. Bộ xuất phải xử lý trên bản sao, giữ hình/định dạng/vùng in cần thiết và loại cột biển do người dùng nhập.

## Kiểm tra thực tế đã làm và giới hạn

- Chạy toàn bộ pytest; chạy thật hai lệnh lập phương án: ví dụ vạch mép có ba khoảng, hai đề xuất và một khoảng bị chặn do thiếu căn cứ chuyển hướng; ví dụ 4.4 có một nhóm ngã tư, tạo một ô đề xuất.
- Quét thư viện và dựng/truy vấn SQLite từ PDF/DWG metadata/LIN thật; dữ liệu chi tiết nằm trong `local-manifests/`, bị loại khỏi Git.
- Harkness chọn luồng standard; daemon địa phương đã khởi động, hồ sơ F-001 được tạo. CLI bản biên dịch thiếu package nội bộ nên đã dùng runtime TypeScript hiện có. Không coi hồ sơ tự sinh là bằng chứng đã thẩm tra độc lập.
- Cổng 8050 không còn nghe và không có phiên acad khi kiểm tra. Hai tiến trình Core Console riêng bị giới hạn sau 30 giây ở bước nạp thành phần Civil, trước khi có báo cáo đối tượng. File mẫu gốc giữ nguyên SHA `b7c24d3f5d5cfaed83884ad570245379e5c1da5a14ca15dc1df0d3dd596692ce` trong phép kiểm tra trước/sau lần thứ hai.
- Đã chuẩn bị bộ đọc side-database `cad/AtgtInspection` và runner `scripts/inspect_dwg.py`. Build .NET đạt với ba cảnh báo tham chiếu assembly Autodesk; **chưa xác minh thực thi**. Không có ghi chú DWG nào được xác nhận kiểu đối tượng hoặc hình thức trình bày.
- Người dùng đã chọn **để phần đọc ghi chú sang lượt sau**. Không tiếp tục thử Core Console hoặc gọi Civil sau quyết định đó.

## Thứ tự làm tiếp

1. Mở mẫu DT.633, xác nhận MCP và định danh bản vẽ; đọc mũi tên, text/lý trình, nhóm biển, style và cách bố trí. Tay Vân Canh là nguồn bổ sung. Không tạo lại thư viện vạch sơn.
2. Thử trên bản sao đoạn ngắn có mép ngoài, dải phân cách, nhánh dân sinh; kiểm tra đường cong, bề rộng thay đổi và phạm vi cấm dừng. Duyệt hình học template và block 7.6/9.3.
3. Hoàn thiện dữ liệu ngữ nghĩa bình đồ và bộ ghi theo mã sở hữu/phiên chạy, kiểm tra đọc lại. Tách khoảng cách curve, lý trình alignment và chiều dài thực của đường offset.
4. Đo bóc theo đối tượng đã đọc lại, xuất Book2.xlsx; loại cột biển giữ thủ công. Kiểm tra công thức, hình, tổng theo đoạn và vùng in trong Excel thật.
5. Kiểm chứng luồng Orca → Antigravity → MCP bằng nhiệm vụ thật và bộ tình huống chuyên môn có đáp án; chưa đánh dấu hoàn tất hệ thống trước bước này.

**Trạng thái: hoàn tất đợt rà soát và phần lập phương án nêu trên; toàn hệ thống còn một phần, CAD/Excel chưa nghiệm thu.**
