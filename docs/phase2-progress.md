# Phase 2 — triển khai kho tri thức và tài sản CAD (24/10/2026)

**Trạng thái: đang triển khai**. Đã nhận và giải nén Library.rar do người dùng gửi; chưa thao tác Civil 3D và chưa tự bố trí biển/vạch.

## Những gì đã thực hiện

1. `src/atgt/assets.py`: kiểm kê DWG theo đường dẫn tương đối, SHA-256, kích thước, phiên bản header và mã biển ứng viên. **Không** tự xác nhận mã biển từ tên file; trạng thái ban đầu `unverified`.
2. `src/atgt/linetypes.py`: đọc các linetype AutoCAD đơn giản, kiểm tra cấu trúc, tổng độ dài chu kỳ và độ dài nét sơn. Những trị số chỉ là **mô tả tài sản**, không phải quy tắc thiết kế đã duyệt.
3. `src/atgt/knowledge.py`: kho SQLite có phiên bản, căn cứ và trạng thái `draft/approved/retired`. Không đưa quy tắc `draft` vào thi hành; tự động thiết kế chỉ cho `ordinary` và `divided_rural`.
4. `data/rules/qcvn41-table2-draft.json`: chép dữ liệu hệ số kích thước biển QCVN 41:2024 Điều 12 Bảng 2 ở trạng thái `draft`, giữ ngoại lệ.
5. `scripts/scan_atgt_library.ps1`: tiện ích quét thư viện Windows tại đường dẫn do người dùng chỉ định; không sửa/chèn DWG.
6. Mẫu Excel chính thức do người dùng xác nhận là `Book2(1).xlsx`, SHA-256 `19672f2be596f471afbfeef0294b1831e1c148a14030dcc901f71f39f8d73985`.

## Kết quả tài sản đã tiếp nhận

- `VACH_SON_QCVN41_2024.lin`: SHA-256 `e4484f094b128c53914b91b1c88bfc6b8b6263452a6767c1346f8427a3b15c99`; parser đã đọc được **14 linetype**, nhưng **chưa** thẩm định theo phụ lục G của QCVN 41:2024.
- `TEMPLATE_VACH_SON_ATGT_QCVN41_2024.dwg`: SHA-256 `62662e912b2e2756418b68e723ef0a1ade8a3391acc92963580b668c9ae16080`; header `AC1021`; chưa đọc geometry/units trong Civil 3D.
- Nguồn PDF QCVN 41:2024 đã khóa: `84825a72c4605b65485f3d31a606525a9bc96c970a5200defc0781496ddbbd46`.

## Lệnh chạy trên máy Windows có thư viện biển

Tải repository từ GitHub và thực hiện từ thư mục gốc dự án trong PowerShell:

```powershell
py -m pip install -e . pytest
powershell -ExecutionPolicy Bypass -File .\scripts\scan_atgt_library.ps1
py -m pytest -q
```

Mặc định quét:

```text
D:\DOCUMENT\TAI LIEU AUTOCAD\Tool CAD\lispCAD\0. Hay dung\AtgtPro\Library
```

Kết quả là `local-manifests/atgt-signs.json` (chỉ dữ liệu kiểm kê, không sao chép DWG). Có thể chạy trực tiếp:

```powershell
py -m atgt.inventory_cli --sign-library "D:\DOCUMENT\TAI LIEU AUTOCAD\Tool CAD\lispCAD\0. Hay dung\AtgtPro\Library" --output "local-manifests\atgt-signs.json"
```

Đối với tệp LIN, cần đưa `--lin "duong-dan\VACH_SON_QCVN41_2024.lin"` khi chạy lệnh Python.

## Khởi tạo SQLite quy tắc nháp

```powershell
py -m atgt.rule_import_cli --source data\rules\qcvn41-table2-draft.json --database local-manifests\knowledge.sqlite
```

Chưa có thao tác tự duyệt; việc phát hành quy tắc `approved` phải do người kiểm định chuyên môn xác nhận với văn bản nguồn.

## Những phần chưa thể thực hiện

- CloudHarness MCP hiện trả lỗi **HTTP 404** khi mở workspace, nên không thể dùng kết nối này để đọc trực tiếp thư mục `D:\...` trên máy người dùng.
- Đã nhận đủ 338 DWG trong archive Library.rar và kiểm kê SHA-256, header, tên nhóm; còn thiếu công cụ đọc DWG để kiểm định hình học, units, điểm chèn, hướng và kích thước.
- Chưa triển khai kiểm tra hình học/thông số CAD bên trong DWG, Civil 3D/C# writer, đối chiếu 30 ca chuyên môn và xuất Excel thành phẩm.

**Ranh giới an toàn:** không đưa CAD/PDF/Excel nguồn nội bộ lên repository đang ở trạng thái Public.


## Cập nhật sau khi người dùng tải Library.rar (24/10/2026)

- SHA-256 archive: `e471f9644250d15084d5ad0fb79543a5bd7aaff03c06a109afc760a68a3a3011`; kích thước file nén: **55.921.847 byte**.
- Đã giải nén thực tế **338 DWG, 69.791.520 byte**; tất cả có header `AC1021`, SHA-256 riêng và không rỗng.
- Kiểm kê theo thư mục: `Bien_Cam` 69; `Bien_Chi_Dan` 122; `Bien_Hieu_Lenh` 33; `Bien_Nguy_Hiem` 83; `Bien_Phu` 31 — **khớp 100% số lượng ghi trong plan**.
- Thêm metadata khóa nguồn ở [`data/source-locks/sign-library-summary.json`](../data/source-locks/sign-library-summary.json). **Không commit** byte DWG nguồn vì repository đang public. Catalog 338 dòng đầy đủ cung cấp riêng ở cuộc trò chuyện.
- Trong thư viện còn 2 file khóa AutoCAD `.dwl`/`.dwl2`, đã loại khỏi bộ 338 DWG.
- Tất cả mã biển vẫn **chưa kiểm định**. Kiểm tra cẩn thận `Bien_Cam/135.dwg` vì mã tham chiếu có tiền tố `DP.135` và `Bien_Chi_Dan/420.dwg` vì `R.420`; 21 mã họ đặc biệt E/G/H và 7 file có hậu tố biến thể cần đối chiếu ảnh/hình học và quy chuẩn. Không coi thư mục là căn cứ gắn tiền tố chuẩn.
- Bước tiếp theo: mở DWG bằng Civil 3D/ODA hoặc nguồn tương thích, đọc units/point/extents/layer/block/attributes và tạo preview; đánh dấu trạng thái kiểm định cho từng asset, sau đó kiểm tra chèn vào DWG thử.
