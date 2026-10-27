# Quy tắc vạch sơn đang triển khai

Ngày 24/10/2026. Các hàm trong tài liệu trả về **phương án dự kiến**, chưa gửi lệnh vẽ.
Nguồn QCVN: bản PDF 403 trang, SHA-256 `84825a72c4605b65485f3d31a606525a9bc96c970a5200defc0781496ddbbd46`.

> Tài liệu này giải thích và dẫn nguồn cho con người, không phải nơi agent nạp quy tắc. Nguồn máy đọc duy nhất cho quy tắc dự án là `D:\DOCUMENT\TCVN\TIEU CHUAN TK ATGT\ATGT_PROJECT_RULES.toml`, được MCP khóa theo `ruleset_id` và SHA-256.

## Vạch 3.1a và 3.1b

`atgt.edge_rules.propose_edge_marking` áp dụng cho từng khoảng đã phân loại trên đường thông thường hoặc đường đôi ngoài đô thị.

| Thông số | Giá trị | Nguồn / cách hiểu |
|---|---|---|
| Mép nhựa ngoài | Tim vạch cách mép 0,30 m, dịch vào phía phần xe chạy | Thực hành do người dùng chỉ định |
| Mép dải phân cách | Tim vạch cách mép 0,50 m, dịch vào phía phần xe chạy | Thực hành do người dùng chỉ định; không gán thành khoảng cách bắt buộc QCVN |
| Bề rộng | 0,15–0,20 m; đầu vào phải chọn rõ | G1.3(a), trang 167 |
| Khoảng hở mép ngoài vạch–mép phần xe chạy | 0,15–0,30 m trong phạm vi quy định | G1.3(a), trang 166; khác cách đo đến tim vạch |
| 3.1a | Liền nét, trắng | G1.3(a) |
| 3.1b | Nét 0,6 m, hở 0,6 m, trắng | G1.3(a), trang 167 |

Với tim cách mép 0,30 m: vạch rộng 0,20 m còn khoảng hở 0,20 m; vạch rộng 0,15 m còn khoảng hở 0,225 m. Công thức: `khoảng hở = khoảng cách tim − bề rộng / 2`.

Điều kiện trước khi đề xuất:

- Có ảnh chụp dữ liệu bản vẽ theo phiên bản (`snapshot_id`), tim tham chiếu, handle mép, căn cứ nhận diện mép và chiều tuyến.
- Xác nhận mép nhựa được dùng tương ứng mép ngoài phần xe chạy; không tự đồng nhất mép bó vỉa, lề gia cố và mép làn xe.
- Kiểm tra đủ bề rộng phần mặt đường chứa toàn bộ nét sơn. Đường có bề rộng phần xe chạy dưới 7 m phải có căn cứ trường hợp cần thiết theo G1.3(a).
- Khoảng đường liên tục đề xuất 3.1a. Khoảng giao đường dân sinh/lối mở chỉ đề xuất 3.1b khi có xác nhận cho phép chuyển hướng và phạm vi khoảng mở đã đo.
- Chưa biết hoặc không cho phép chuyển hướng thì giữ khoảng đó ở trạng thái cần xử lý; không dùng 3.1a làm bằng chứng cấm rẽ. Ý nghĩa vạch 3.1 không phải tự thân cấm mọi thao tác đè vạch.
- Khu vực tách/nhập làn, làn chuyển tốc hoặc phân chia làn xe thô sơ cần quy tắc riêng; không chuyển mọi nét đứt thành 3.1b.

Trong LIN được cung cấp, chọn `VACH_3.1B_0.6M` nếu mẫu nét đúng `A,0.6,-0.6`. Hai biến thể 1/1 m và 2/2 m không được tự thay thế cho quy cách 3.1b này. `.lin` không chứng minh bề rộng polyline, đơn vị DWG hoặc tỷ lệ nét thực tế: phải kiểm tra các yếu tố này khi vẽ.

```powershell
python -m atgt.planning_cli --kind edge --input examples/edge-contexts.json --lin "E:\TEMPLATE CV\BINH DO ATGT DU AN MAU\VACH_SON_QCVN41_2024.lin" --output local-manifests/edge-preview.json
```

Ví dụ là dữ liệu giả định, có chủ đích để một khoảng mở dải phân cách thiếu thông tin chuyển hướng bị chặn. Không dùng các handle/vị trí ví dụ để vẽ.

## Vạch 4.4: sử dụng lại skill đã có

Nguồn: `ve-vach-son-mac-vong-4-4-qcvn41-2024`, script `scripts/ve_vach_44.py`.
SHA-256 script tại thời điểm đọc: `c5df1f9255e29a530cb164c561b9c1217b97292bab2cfb065b0d9187614e842a`.

`skill44_classifier.py` giữ lại nguyên hàm phân loại thuần Python từ skill. `box44_rules.py` kiểm tra đầu vào rồi gọi hàm đó. Không nạp client MCP và không gọi phần xóa/vẽ của script cũ.

| Tình huống từ skill | Kết quả phân loại |
|---|---|
| Một nhánh, không có nhánh đối diện trong 30 m | Một ô phía có nhánh |
| Hai nhánh đối diện, độ lệch ≤ 5 m | Một ô chung |
| Hai nhánh đối diện, 5 m < độ lệch ≤ 30 m | Hai ô so le, phía nào ô đó |

Các ngưỡng 5 m và 30 m là **quy tắc thực hành từ skill**, không phải trích dẫn ngưỡng bắt buộc trong QCVN. QCVN G1.4(e), trang 177–178, Hình G.38–G.39 xác định ý nghĩa chống dừng gây ùn tắc, vị trí áp dụng và quy cách kiểu đơn giản màu vàng, nét 20–40 cm. Chọn 20 cm theo cấu hình skill. Kiểu mắt võng thông thường có quy cách khác, chưa nằm trong hàm này.

Các điều chỉnh tích hợp:

- Phải có căn cứ bố trí vùng không dừng; tồn tại vạch 3.1b chưa đủ để tự đặt 4.4.
- Dùng bề rộng đã đo, truyền `default_lane_w=0` để loại việc tự nâng lên tối thiểu 3,7 m.
- Có nhiều nhánh đối diện cùng nằm trong phạm vi ghép thì báo mơ hồ; không để thứ tự danh sách quyết định ghép cặp.
- Chưa áp dụng sơ đồ ô chung vượt qua dải phân cách. Đường đôi cần xử lý riêng từng phần xe chạy và biên đảo/dải phân cách trước khi bật quy tắc này.
- Bề rộng biến thiên chưa được chứng minh thì chờ thiết kế hình học. Không lấy trung bình bề rộng để khẳng định cả ô nằm trong mặt đường.
- Giữ nguyên nguyên tắc dùng Curve API bản địa. `GetDistAtPoint` trả về khoảng cách dọc curve; muốn ghi lý trình Civil phải xét tim, gốc tuyến và station equations. Không coi hai đại lượng là một.
- Sau khi dựng bốn đỉnh vẫn phải kiểm tra bao nét sơn trên đoạn cong; việc điểm nằm trên đường cong không tự chứng minh các cạnh nối thẳng nằm trong phạm vi cần sơn.
- Bộ ghi CAD tương lai chỉ cập nhật đối tượng có mã sở hữu do hệ thống tạo, không xóa toàn layer `vach 4.4`. Phải đọc lại kết quả trước khi đưa vào thống kê.
- Diện tích mắt võng phải xử lý giao nhau giữa khung và đường chéo theo quy tắc đo bóc được chốt, không mặc định cộng chiều dài × bề rộng gây đếm trùng.

```powershell
python -m atgt.planning_cli --kind box44 --input examples/box44-contexts.json --output local-manifests/box44-preview.json
```

## Ghi chú biển và thống kê

Nguồn mẫu duy nhất do người dùng chọn ngày 25/10/2026 là `BD TK ATGT TAY VAN CANH.dwg`; không dùng DT.633. Kiểm kê live trên MCP 8070 xác nhận mẫu chủ đạo là `LEADER` cổ điển 3 đỉnh trên layer `BIEN-BAO`, dimstyle `duonggiao`, chữ `DBText` ARIALH cao 2,0 và block biển tại đỉnh cuối. Archetype chuẩn được nhận dạng bằng quan hệ hình học của `km7+409` + block `207a_245a`, không dùng handle vì `Wblock` đổi handle.

Mẫu chuẩn có đoạn leader đầu khoảng 20,1478 m, đoạn cuối khoảng 3,8420 m; chữ cách đỉnh mũi tên khoảng 5,3405 m. Đây là thông số trình bày của dự án mẫu, không phải quy định QCVN. Các mẫu I.439, leader 2 đỉnh, ISO-25 và nền vàng là ngoại lệ, chưa được tự động hóa. Lý trình dự án mới vẫn phải tính từ đúng tim/station equation; ký hiệu trình bày không quyết định kích thước mặt biển thực tế.

MCP `atgt-cad` clone text/leader theo phép quay+dời quanh điểm chèn biển, tạo block theo tên đã có trong bản làm việc, gắn XData `ATGT_AGENT`, rồi đọc lại loại đối tượng, nội dung, layer, block, rotation, scale và quan hệ điểm. Chỉ cụm đủ ba phần mới được ghi receipt xác minh.

Mẫu Excel hiện hành là `Book2.xlsx`, SHA-256 `19672f2be596f471afbfeef0294b1831e1c148a14030dcc901f71f39f8d73985`. Loại cột biển do người dùng nhập, không suy ra và không tính khối lượng cột. Chỉ dùng đối tượng CAD đã đọc lại, không lấy khối lượng dự án mẫu hoặc độ dài chênh lý trình để thay thế chiều dài sơn thực trên đường cong.
