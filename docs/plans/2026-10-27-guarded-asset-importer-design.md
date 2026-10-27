# Guarded asset importer — 27/10/2026

## Mục tiêu

Agent chọn tài sản theo mã nghiệp vụ nhưng không được tự truyền đường dẫn file hoặc đoán tên block. Catalog là snapshot có `catalog_id`, SHA-256 của chính catalog và SHA-256 từng DWG nguồn. Chỉ bản ghi `approved_for_insert` có đủ kiểm tra hình học/đơn vị mới được nhập.

## Luồng

1. `atgt_cad_list_assets` tìm theo `kind`, `code`, `status` và trả `asset_id`.
2. Sau khi tạo/activate work copy và đồng bộ đơn vị, `atgt_cad_import_assets` nhận tối đa 50 `asset_id`.
3. Biển dạng whole-DWG được đưa vào block table bằng tên đích ổn định; vạch 7.6/9.3 clone đúng named block đã duyệt từ template.
4. Block definition nhận XData `ATGT_AGENT` gồm import id, asset id, hash, code và kind. `atgt_cad_verify_asset_import` đọc lại độc lập trước khi ghi receipt.
5. Lệnh đặt chỉ nhận `asset_id`; tên block, tỷ lệ gốc và góc hiệu chỉnh lấy từ receipt. BlockReference tiếp tục mang asset id/hash và được kiểm tra vị trí, góc, scale sau write.

Một `import_id` đã có plan không bao giờ lặp write mù. Lời gọi lại chỉ đọc block table để reconcile, phù hợp trường hợp timeout nhưng Civil có thể đã hoàn tất thao tác.

## Catalog đầu tiên

`ATGT-ASSETS-20261026-V1` khóa tám block 7.6/9.3 trong `TEMPLATE_VACH_SON_ATGT_QCVN41_2024.dwg`. Kích thước hình học đã đọc bằng side database và được hiểu theo mét dù header template khai báo Feet; việc này được ghi rõ trong evidence từng asset. `Bien_Cam/102.dwg` có extents 7 x 7 và INSUNITS Inches nên chỉ vào hàng chờ review, không được chèn.

## Ranh giới nghiệm thu

Test và bắt tay stdio chứng minh schema, khóa đường dẫn/hash, idempotency và 17 tool. Chỉ một phiên Civil đang mở đúng nguồn, import vào work copy, đọc lại và kiểm tra trực quan mới chứng minh chèn live.
