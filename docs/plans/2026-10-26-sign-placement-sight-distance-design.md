# Thiết kế rule vị trí biển theo QCVN và tầm nhìn hãm xe

## Quyết định

Bổ sung hai nhánh đề xuất vào `atgt_evaluate_rules`: `sign_placement` cho một biển/đối tượng và `junction_warning` cho chuỗi W.205/W.207. QCVN-specific distance luôn thắng fallback. Fallback chỉ chạy khi request có bằng chứng tra QCVN và cờ xác nhận không có khoảng cách số; server đồng thời phải khóa đúng PDF TCVN 4054:2005.

Chuỗi nút được xử lý theo chiều xe chạy, không theo thứ tự mảng đầu vào. Khoảng cách giữa hai nút nhỏ hơn S1 tạo một cụm. Cụm toàn đường nhánh không ưu tiên đi theo QCVN C.7(d), chỉ sinh W.207d/e. Cụm cùng cấp hoặc hỗn hợp giữ họ biển của nút đầu tiên người lái gặp, đúng quyết định của người dùng; provenance ghi `user_project_practice`. S.501 dùng khoảng cách từ biển đến nút cuối và làm tròn hàng chục.

## Biên an toàn

- Không suy ra tốc độ, ưu tiên, phía nhánh hoặc biến thể từ layer.
- Không coi S1 là bằng chứng tầm nhìn thực tế thông thoáng.
- Thiếu hash TCVN, bằng chứng tra QCVN, station range hoặc geometry/priority evidence thì chặn.
- Kết quả chỉ là proposal, không mở rộng quyền của `atgt-cad`.

## Kiểm thử sở hữu hợp đồng

Owner là hàm thuần trong `sign_placement_rules.py`. Ca chính bảo vệ đủ bảy giá trị Bảng 10, precedence QCVN, fail-closed khi thiếu nguồn, ngưỡng gom `< S1`, lựa chọn W.207d/e, bảo toàn họ W.205/W.207 trong cụm hỗn hợp và phép làm tròn S.501. Kiểm thử stdio chỉ giữ rủi ro riêng của giao thức: schema nhận request mới và thiếu nguồn TCVN phải bị chặn.
