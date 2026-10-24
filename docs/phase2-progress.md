# Phase 2 — triển khai kho tri thức và tài sản CAD (24/10/2026)

**Trạng thái: đang triển khai**, chưa có quyền đọc thư viện DWG trên máy Windows, chưa thao tác Civil 3D, chưa tự bố trí biển/vạch.

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
- Chưa có dữ liệu byte của 338 DWG trên môi trường phân tích; chưa thể xác minh kiểm kê gốc (69/122/33/83/31).
- Chưa triển khai kiểm tra hình học/thông số CAD bên trong DWG, Civil 3D/C# writer, đối chiếu 30 ca chuyên môn và xuất Excel thành phẩm.

**Ranh giới an toàn:** không đưa CAD/PDF/Excel nguồn nội bộ lên repository đang ở trạng thái Public.
