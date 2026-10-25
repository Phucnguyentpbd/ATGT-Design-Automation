# Xuất bảng thống kê theo Book2 — 25/10/2026

## Kết quả và phạm vi

Bộ xuất tạo bản sao theo hai sheet của Book2: `KL VACH SON` và `THONG KE BIEN BAO ATGT`. Đầu vào là số liệu đo bóc đã được kiểm tra, không phải đối tượng đề xuất. Đã thử bằng dữ liệu giả định, tính lại trong Excel 16.0 và kiểm tra bản in. Chưa đo bóc bản vẽ dự án thật; nguồn CAD và cách ghi chú lý trình vẫn chờ lượt đọc Civil tiếp theo.

File mẫu được khóa SHA-256 `19672f2be596f471afbfeef0294b1831e1c148a14030dcc901f71f39f8d73985`. Không sửa Book2 gốc. Nếu người dùng đổi mẫu, phải kiểm kê lại cấu trúc và kiểm tra bản in trước khi thay mã khóa.

## Quy tắc thống kê

- Vạch sơn: giữ các hàng theo mẫu, chia khối lượng theo đoạn và cộng tổng bằng công thức. Phân biệt lớp sơn 2 mm/6 mm theo hàng của mẫu; đây là cấu hình hồ sơ, không suy ra độ dày từ QCVN 41.
- Mỗi đoạn/hạng mục phải khai báo phạm vi đã đo đủ. Có xác nhận đo đủ nhưng không có đối tượng thì bằng 0. Chưa xác nhận thì ghi `Chưa đo đủ`; tổng liên quan ghi `Chưa đủ`, không cộng thiếu rồi báo là tổng hoàn chỉnh.
- Diện tích đầu vào là diện tích sơn đã đo. Không lấy dài tuyến nhân hệ số từ công thức dự án cũ. Cột chiều dài/số lượng C của mẫu hiện để trống: ledger chưa cung cấp chiều dài/số nét độc lập đủ căn cứ; cột D nêu cách đo, F trở đi ghi diện tích/khối lượng.
- Với 4.4, phiên bản hiện tại nhận `paint_union_area`: diện tích vùng sơn thực tế đã hợp hình, không tính trùng chỗ các nét giao nhau. Đây là quy ước đo hình học của bộ xuất; không tuyên bố là điều khoản thanh toán của QCVN. Nếu hồ sơ dự án quy định cách bóc khác, cần bổ sung quy tắc đo riêng đã được chấp thuận.
- Mặt biển được nhóm theo **mã đầy đủ + hình dạng + kích thước thật + công tác**. `P.102` cỡ 700 và 900, hoặc lắp mới/giữ lại/di dời, là các nhóm khác nhau.
- Mỗi dòng chi tiết chứa tối đa ba mặt biển theo mẫu. Cụm bốn mặt trở lên nối thêm dòng cùng mã cụm, không bỏ mặt thứ tư và không tự tách thành cột biển mới.
- Cột O chỉ dành cho người dùng phân loại cột; không tham gia tổng hợp. Giữ trạng thái ẩn của mẫu. Có thể bỏ ẩn để nhập tay, rồi dùng `--previous` khi xuất phiên bản kế tiếp.
- Cột Q chứa mã cụm, R:T chứa công tác từng mặt để công thức tổng hợp phân biệt đúng. Các cột này được ẩn. Không tự sửa mã cụm; đây là khóa để giữ dữ liệu nhập tay khi đổi thứ tự/lý trình.
- Nếu cụm đã có phân loại thủ công bị xóa khỏi ledger, bộ xuất dừng để xử lý dữ liệu đó, không âm thầm bỏ mất. Nếu cùng một cụm có hai giá trị thủ công mâu thuẫn hoặc workbook thuộc dự án khác thì cũng dừng.

## Hợp đồng đầu vào

Xem `examples/quantity-ledger-demo.json` để có ví dụ đầy đủ, được gắn rõ `data_kind: synthetic`.

| Nhóm | Thông tin bắt buộc |
|---|---|
| `project` | Mã dự án ổn định, tên và phụ đề bảng |
| `snapshot` | Mã snapshot, trạng thái đã đọc lại CAD và đường dẫn/tham chiếu bằng chứng |
| `segments` | Mã đoạn, mã tim, đầu/cuối phạm vi và nhãn cột; không chồng lấn trên cùng tim |
| `coverage` | Đoạn, mã hạng mục, độ dày, đã đo đủ hay chưa và bằng chứng |
| `quantities` | Mã phép đo, mã đối tượng, đoạn/hạng mục, đơn vị, lượng đo, phương pháp đo, snapshot và bằng chứng |
| `clusters` | Mã cụm, tim tham chiếu, lý trình đã xác minh, phía trái/dải giữa/phải |
| `faces` | Mã mặt, mã cụm, mã biển, hình, kích thước mm, công tác, tài sản và bằng chứng đọc lại |

`sign_coverage_complete=true` xác nhận việc kiểm kê mặt biển trong phạm vi báo cáo đã đủ. Bản ghi thiếu bằng chứng, trùng đối tượng/đoạn/hạng mục, sai đơn vị, snapshot cũ hoặc chưa xác minh bị chặn. Các cờ xác minh do bước đọc CAD cung cấp: bộ xuất kiểm tra hợp đồng, chưa tự mở DWG để chứng thực nội dung đó.

Lý trình `station_m` là lý trình đã giải quyết gốc tuyến/station equations ở bước trước. Bộ xuất chỉ định dạng và làm tròn đến 0,01 m, không chuyển khoảng cách hình học thành lý trình Civil.

## Chạy

Cài package Python theo README. Node và `@oai/artifact-tool` lấy từ môi trường công cụ đã cài; không thêm phụ thuộc Node vào repo. Các đường dẫn bên dưới là ví dụ Windows của máy triển khai, có thể thay theo host.

```powershell
$python = 'C:\Users\PHUC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$node = 'C:\Users\PHUC\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$nodeRuntime = 'C:\Users\PHUC\.cache\codex-runtimes\codex-primary-runtime\dependencies\node'
$env:PYTHONPATH = 'src'
& $python scripts/export_book2.py `
  --ledger examples/quantity-ledger-demo.json `
  --template 'C:\Users\PHUC\Desktop\Book2.xlsx' `
  --output 'outputs/demo/ATGT_KIEM_THU.xlsx' `
  --node $node --node-runtime $nodeRuntime `
  --evidence-dir 'local-manifests/export-demo'
```

Xuất lại: thêm `--previous 'outputs/du-an/lan-01.xlsx'`, dùng cùng `project.id` và các `cluster_id` ổn định, ghi `--output` sang file phiên bản mới. Chỉ phần phân loại cột O được nhập lại từ workbook trước; các sửa số liệu khác cần cập nhật ledger có căn cứ, không tự nhập ngược vào dữ liệu CAD.

Bộ xuất lưu kế hoạch ô, ảnh kiểm tra và báo cáo cục bộ. `native_excel_verified=false` trong báo cáo của CLI là chủ ý: tạo XLSX không chứng minh Excel thật đã mở và tính đúng. Bằng chứng kiểm tra Excel được lập riêng sau mỗi đợt nghiệm thu.

## Cách giữ đúng mẫu

Artifact Tool ghi nội dung, công thức, định dạng và ảnh xem trước. Hai bước XML hẹp chỉ bù các chức năng còn thiếu của thư viện:

1. Trên bản sao trung gian, xóa số liệu/công thức chia sẻ của dự án cũ **chỉ trong các vùng sẽ thay**, để có thể ghi dữ liệu mới.
2. Sau khi xuất, giữ nguyên byte ảnh EMF, bỏ tên vùng hỏng/liên kết cũ và danh sách chọn của dự án mẫu, khôi phục vùng in/lặp đầu bảng/A4 ngang. Kiểm tra ô lưu lỗi trước khi công bố file; ghi qua file tạm rồi mới thay đầu ra.

Ba đoạn như mẫu in vừa chiều ngang. Trên ba đoạn, giữ tỷ lệ 75% và lặp A:E trên các trang ngang để tránh co chữ quá nhỏ. Hỗ trợ tối đa 100 đoạn, nhưng nghiệm thu thực tế hiện mới có trường hợp 3 và 4 đoạn; dự án nhiều đoạn cần xem lại bản in. Hình minh họa vẫn được giữ tại vị trí nguồn, nằm ngoài vùng in bảng.

## Bằng chứng đã chạy

- 97 kiểm thử Python toàn repo đạt; 15 ca thuộc hợp đồng xuất/giữ dữ liệu thủ công. Đã thấy lỗi định dạng Km0+1000, bỏ mất phân loại của cụm bị xóa, nhận sai phương pháp đo và phụ thuộc tên part `sheet2.xml` trước khi sửa.
- Chạy thật CLI với Book2 nguồn: giữ ảnh EMF, loại 4.250 tên vùng hỏng, không sửa file nguồn.
- Excel 16.0 tính tổng bộ **giả định**: 3.1a = 500 m², 3.1b = 28,8 m², 4.4 = 13,6 m², tổng nhóm 2 mm = 542,4 m². Bảy mặt biển vào sáu nhóm, số lượng 2/1/1/1/1/1.
- Đổi thử F11 từ 200 thành 210 trên bản kiểm thử: tổng hàng tăng 10 m² và tổng nhóm tăng tương ứng. Đổi cỡ một mặt P.102 700 thành 900: nhóm 700 giảm một, nhóm 900 tăng một. Bản giao không chứa thay đổi thử này.
- Excel không báo lỗi công thức; hai sheet in thành hai trang A4 ngang, đã xem ảnh từ PDF in bằng Excel.
- Nhập tay phân loại C1/C2, đổi thứ tự cụm, chạy `--previous`, rồi mở lại bằng Excel: giá trị đi theo đúng mã cụm. Thêm đoạn thứ tư chưa đo: tổng báo chưa đủ, lặp cột A:E và tỷ lệ 75% được Excel nhận đúng.

Đây là nghiệm thu bộ xuất trên dữ liệu giả định. Tích hợp Orca → Antigravity → Civil, xác minh tài sản và đo bóc dự án thật vẫn là bước kế tiếp.
