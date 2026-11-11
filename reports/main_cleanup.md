# Rà soát và dọn main — 12/11/2026

Nhánh `refactor/main-cleanup` xuất phát từ `main` tại `2988e67` (PR #13). Mục tiêu là loại các đường chạy/báo cáo đã bị thay thế, sửa mô tả và giữ khả năng tái lập kết quả chuẩn.

## Phần đã bỏ

- Luồng SARIMAX tính nhân sự tổng đài theo productivity 3 calls/person-hour và chi phí giả USD; CLI standalone vehicle-plan cũ. Kế hoạch xe hiện dùng duy nhất pipeline chung trong `run_queuing.py`.
- Dự báo/checkpoint SARIMAX refit cũ ở root/rerun và báo cáo staffing/cost của chúng; giữ kết quả 1h/no-refit 24h.
- Checkpoint LSTM `vanilla_seq24` và hình minh họa cũ; giữ `vanilla_1h_rolling`, `vanilla_24h_block`, hai scalers và kết quả 24h.
- Export web dựa trên weights cũ, bảng root hai mô hình và metadata “ARIMA chưa có”; snapshot hiện dùng profiles/operations. Chuẩn bị snapshot từ đầu bằng prepare_dashboard rồi prepare_operations.
- Hàm chart/scenario/replay của giao diện cũ không còn caller; giữ xuất CSV và các hàm dashboard/operations đang dùng.
- Script nhập HTML/font một lần có thể ghi đè giao diện hiện tại, generator LSTM phiên bản cũ; giữ generator hiện hành và DOM QA.
- Font WOFF2 IBM không được tham chiếu, icon SVG cũ; giữ IBM TTF còn được CSS nền tham chiếu và font Zenless.
- Nhật ký merge/deploy lỗi thời, báo cáo LSTM cũ; README và các tài liệu hiện hành đã được viết lại. Các phiên bản cũ còn trong Git history.

SARIMAX mặc định được đưa về protocol chuẩn: toàn bộ train, no-refit, output `norefit`. Forecast evaluation tách riêng khỏi staffing, có kiểm tra alignment/interval và kiểm thử. Thử nghiệm refit vẫn có thể gọi rõ ràng nhưng phải dùng output riêng. Các con số dự báo, model weights hiện hành và công thức bố trí ca được giữ nguyên; chỉ sửa mô tả comparability sai trong metadata SARIMAX.

## Phần giữ và giới hạn

`data/*.csv`, checkpoint hiện hành, dự báo chọn trên validation, output kế hoạch xe và audit busy-time được giữ vì dùng trong inference, kiểm thử hoặc truy nguyên khoa học. Dung lượng lớn không đồng nghĩa không dùng. Notebook EDA gốc và output thí nghiệm được giữ; định nghĩa target đã đối chiếu có ưu tiên hơn mô tả distinct-call cũ.

Kernel busy-time hiện là hằng số kế thừa, không được script audit duration tự động sinh lại. `rho`, P90 và các tiêu chí Erlang/Poisson là giả định kịch bản, chưa có bằng chứng bảo đảm SLA. Nhãn “thực cần” trong một số output cũ là nhu cầu đối chiếu theo mô hình, không phải roster thực tế. LSTM train/val khối vẫn có padding cuối như khi huấn luyện weights; thay cách này cần thí nghiệm mới. Timestamp nghiên cứu chưa chuẩn hóa DST.

Không huấn luyện lại mô hình trong đợt dọn này. Không thay dữ liệu cố định bằng nguồn DataSF mới có revision. Chỉ kiểm tra local và đóng gói thử; không commit, push hoặc triển khai lên VPS trong tác vụ này.

## Kiểm chứng

- Bộ Python: 66 tests đạt sau các thay đổi chính; 11 tests SARIMAX đạt sau khi thêm chặn refit ghi đè output chuẩn (tổng cộng 67 test cases hiện có).
- 11 tests JavaScript đạt; kiểm tra 60 tổ hợp kế hoạch/ca/chi phí khớp báo cáo Python; DOM QA đạt.
- Tạo snapshot từ đầu trong thư mục tạm khớp toàn bộ bốn profile và 6.796 hàng vận hành đã lưu.
- Dữ liệu/weights/dự báo hiện hành không đổi; forecast plots SARIMAX được dựng lại từ CSV để ghi đúng đơn vị lượt điều động. Gói release thử đạt kiểm tra checksum, routes, assets và API local.
- Mọi liên kết tài liệu local đã kiểm tra. Các cảnh báo thư viện Prophet/pandas, PyTorch pin_memory và statsmodels vẫn hiện trong test; không làm test thất bại.

Đã bỏ 49 file tracked bị thay thế, khoảng 33.82 MiB trong working tree. Điều này không thu nhỏ Git history. API snapshot lịch sử không còn root `rows` legacy; consumer ngoài giao diện hiện hành nếu dùng trường đó cần chuyển sang `profiles`.
