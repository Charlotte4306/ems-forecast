# SARIMAX và kịch bản năng lực điều phối

## Nguồn và tích hợp

Code ban đầu từ `origin/thuyduong`, commit `ae4ca84`, phát triển trên main
`199e394`. Nhánh `refactor/integrate-sarimax` tích hợp phần này mà không thay đổi
pipeline LSTM và Prophet. Dữ liệu vẫn là sáu CSV chung, không đổi timezone.

Các sửa đổi:

- Dùng `ems.paths`, kiểm tra dữ liệu chung và `compute_metrics`.
- Thêm CLI `main.py sarimax`, main guard và dependency `statsmodels`.
- Sửa `fillna(ndarray)` bằng Series có cùng index.
- Tách xây đặc trưng, rolling forecast, huấn luyện và đánh giá năng lực.
- Không tắt toàn bộ warnings; loại ứng viên không hội tụ và từ chối xuất mô hình cuối không hội tụ.
- Chọn theo MAE đầy đủ; chỉ làm tròn khi hiển thị.
- Dùng Powell mặc định: thử L-BFGS trên cấu hình đầu đã không hội tụ sau 300
  vòng lặp; Powell hội tụ trong kiểm tra trên cùng dữ liệu. Có thể chọn lại
  `--optimizer lbfgs`; thuật toán tối ưu được lưu trong metadata.
- Lưu bảng validation, model, hash dữ liệu, phiên bản thư viện, cấu hình và metrics.
- Dùng `extend` để cập nhật trạng thái thay vì lọc lại toàn bộ lịch sử bằng `append`.
  Tests đối chiếu hai cách trên cùng tham số và kiểm tra không dùng trước quan sát trong đợt dự báo.

## Quy trình

1. Tạo Fourier theo giờ (K=3 hoặc 4), tương tác cuối tuần, thứ trong tuần và
   ngày lễ liên bang Mỹ. Lịch ngày lễ được tạo theo khoảng ngày dữ liệu.
2. Fit 8.760 giờ cuối train cho năm ứng viên ARMA: (1,0,1)/K3, (1,0,1)/K4,
   (2,0,1)/K4, (1,0,2)/K4, (2,0,2)/K4; chọn theo MAE validation.
3. Fit cấu hình thắng trên 8.760 giờ cuối train + validation (năm 2025).
4. Dự báo 24 giờ tiếp theo, lưu dự báo và khoảng trung tâm 80%, sau đó mới
   nhận actual của đợt đó để cập nhật trạng thái. Tham số không được fit lại.
   Đợt cuối có thể ngắn hơn 24 giờ.
5. Cắt dự báo và hai cận về tối thiểu 0. Coverage được đo sau bước này.

Checkpoint lưu trạng thái sau fit năm 2025, trước khi cập nhật bằng test.
File pickle chỉ nên được nạp từ nguồn tin cậy trong môi trường tương thích.

## Kết quả gốc đã kiểm tra lại

Artifact `outputs/sarimax/pred_sarimax.csv` từ nhánh gốc chứa 6.796 giờ,
2026-01-01 00:00 đến 2026-10-11 03:00, khớp toàn bộ timestamp/actual với test.

| Phạm vi | MAE | RMSE | WAPE | Coverage 80% |
|---|---:|---:|---:|---:|
| Toàn test | 3,012259 | 3,888328 | 25,7994% | 81,4303% |
| Bỏ 24 giờ đầu để khớp LSTM | 3,003519 | 3,865561 | 25,7398% | 81,4973% |

Nhánh gốc không lưu cấu hình thắng/checkpoint/phiên bản thư viện. Vì vậy không
thể khẳng định một lần fit mới tái lập chính xác các giá trị gốc này.
Các lần chạy mới có `validation_results.csv`, `metrics.json` và metadata checkpoint.

## Lần chạy kiểm tra sau tích hợp

Để giữ nguyên CSV gốc khi kiểm tra, lần chạy sau refactor dùng:

```powershell
.\.venv\Scripts\python.exe main.py sarimax --output-dir outputs/sarimax/rerun --checkpoint-dir checkpoints/sarimax
```

`outputs/sarimax/rerun/` chứa dự báo/báo cáo mới và bảng validation; checkpoint
trong `checkpoints/sarimax/` thuộc lần chạy này. `outputs/sarimax/pred_sarimax.csv`
vẫn là dự báo của nhánh gốc. Vì thuật toán tối ưu đã đổi và bản gốc không có
metadata huấn luyện, hai bộ kết quả cần được phân biệt khi trình bày.

Cả năm ứng viên đều hội tụ với Powell. Cấu hình được chọn là `(2,0,2), K=4`,
MAE validation `3.0961038455`; mô hình fit cuối cũng hội tụ.

| Phạm vi lần chạy mới | MAE | RMSE | WAPE | Coverage 80% |
|---|---:|---:|---:|---:|
| Toàn test (6.796 giờ) | 2,997401 | 3,866300 | 25,6722% | 81,6363% |
| Bỏ 24 giờ đầu (6.772 giờ) | 2,990696 | 3,849242 | 25,6299% | 81,6893% |

Với cùng giả định năng suất và chi phí, dự báo điểm mới cho tổng chi phí
339.360 USD, giảm 4,25% so với profile lịch sử; đây vẫn là kết quả mô phỏng.

Đánh giá lại riêng bộ dự báo mới bằng:

```powershell
.\.venv\Scripts\python.exe main.py sarimax --evaluate-only --output-dir outputs/sarimax/rerun
```

## Năng lực và chi phí

Giả định mặc định: 3 cuộc gọi/người/giờ; chi phí thừa 30 USD/người-giờ,
chi phí thiếu 75 USD/người-giờ. Số người = ceil(cuộc gọi / năng suất).
Actual chỉ dùng để đánh giá thiếu/thừa sau khi đã xác định lịch theo dự báo.

Trên artifact gốc, baseline lịch sử tốn 354.435 USD; SARIMAX điểm tốn 341.670
USD (giảm 3,6%); dùng cận trên khoảng 80% tốn 412.545 USD nhưng giảm tỷ lệ
giờ thiếu người từ 30,2% xuống 5,6%.

Đây là chi phí giả định; không mô hình hóa hàng đợi, cam kết thời gian đáp ứng,
ca làm, nghỉ giữa ca, thời gian di chuyển hay số xe. Cận trên khoảng trung tâm
80% tương ứng phân vị danh nghĩa 90%, không phải cam kết mức phục vụ 80%.
Giờ thiếu/thừa trong CSV là tổng người-giờ, khác số khung giờ xảy ra thiếu/thừa.

## So sánh với mô hình khác

SARIMAX dùng dự báo nhiều bước, cập nhật mỗi 24 giờ và fit cuối trên năm 2025.
Prophet/LSTM hiện tại dùng lịch sử quan sát theo từng giờ và cutoff huấn luyện
khác; LSTM còn có độ trễ đặc trưng đã ghi nhận trong báo cáo tích hợp.
Chỉ căn timestamp chưa đủ để kết luận mô hình nào tốt hơn. Muốn xếp hạng cần
đồng nhất cutoff, chân trời, thông tin có sẵn và cách cập nhật cho cả ba mô hình.

## Lệnh kiểm tra

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py sarimax --evaluate-only
```

`--evaluate-only` xác minh file dự báo khớp test rồi tạo lại báo cáo; không dùng
checkpoint để tái dự báo và không thay đổi file dự báo đầu vào.

Đã kiểm tra sau tích hợp: 16 tests pass (gồm tests Prophet/LSTM hiện có), chạy
đủ năm ứng viên và test, đánh giá CSV gốc từ thư mục khác, nạp lại checkpoint
và đối chiếu đủ 24 dự báo của block đầu với CSV mới (sai số trong ngưỡng 1e-10).
