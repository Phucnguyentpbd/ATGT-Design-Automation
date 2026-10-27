# Thiết kế ruleset dự án ATGT độc lập

Ngày 26/10/2026.

## Mục tiêu

Agent phải tự nạp xuyên suốt các quy tắc dự án do người dùng duyệt, thay vì bắt người dùng lặp lại trong mỗi prompt. Quy tắc dự án phải tách biệt rõ với văn bản QCVN/TCVN và với ví dụ từ bản vẽ mẫu.

## Nguồn chuẩn duy nhất

`D:\DOCUMENT\TCVN\TIEU CHUAN TK ATGT\ATGT_PROJECT_RULES.toml`

File nằm cạnh bộ quy chuẩn để dễ quản lý nhưng tự khai báo rằng nó không phải văn bản QCVN/TCVN. Mỗi phiên MCP đọc một snapshot bất biến gồm `ruleset_id`, schema và SHA-256. Nếu byte của file đổi trong phiên, mọi lời gọi tiếp theo bị chặn cho tới khi review/version hóa và khởi động lại.

## Luồng agent

1. Gọi `atgt_status` để khóa QCVN, SQLite, LIN, TCVN 4054 và ruleset.
2. Gọi `atgt_get_project_rules(all)` một lần ở đầu task.
3. Giữ `ruleset_id` và `project_rules_sha256` trong các envelope proposal/validation.
4. Tra QCVN/TCVN theo từng quyết định. Quy định cụ thể của QCVN vẫn ưu tiên hơn rule dự án.
5. Chỉ yêu cầu user khai báo dữ liệu thay đổi theo bản vẽ, không hỏi lại các rule đã được nạp.

## Cổng an toàn

- TOML UTF-8, tối đa 128 KiB, schema và các section bắt buộc được kiểm tra khi khởi động.
- Những giá trị đã được code thực thi được kiểm tra chéo; sửa TOML mà chưa sửa/review code sẽ làm server từ chối khởi động.
- `atgt_evaluate_rules` từ chối chạy nếu chưa cấu hình ruleset.
- Rule user có provenance riêng, không được trình bày như trích dẫn QCVN/TCVN.
- Ruleset không cấp quyền ghi CAD; `atgt-cad` vẫn yêu cầu work copy, batch, receipt và read-back.

## Phạm vi file

Ruleset hiện bao gồm: thứ tự nguồn, đầu vào dự án, quan hệ ưu tiên mặc định, vị trí biển và fallback S1, gom W.205/W.207/S.501, 3.1a/3.1b/4.4, archetype leader/lý trình, đường dẫn tài sản, Book2, an toàn CAD và hành vi agent.

Các tài liệu `marking-rules.md` và `sign-placement-rules.md` chỉ còn vai trò giải thích/audit cho con người; chúng không phải nguồn máy đọc thứ hai.
