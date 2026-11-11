# SARIMAX: hai horizon, tham số cố định

`ems/models/sarimax/model.py` tạo calendar/Fourier regressors và forecast rolling; `run_sarimax.py` fit, chọn trên validation và ghi dự báo. Đây là ARMA với biến ngoại sinh lịch/Fourier được triển khai bằng SARIMAX, không phải seasonal SARIMA có seasonal order khác 0.

Target là lượt đáp ứng xe MEDIC theo giờ nhận cuộc gọi. Hai thí nghiệm chuẩn dùng 52.440 giờ train đến hết 2024, chọn theo MAE validation 2025, giữ tham số train khi đánh giá 2026. Validation và các block actual đã quan sát chỉ cập nhật filter state. Không quan sát actual trong block đang dự báo.

| Artifact | Horizon | Order, K | MAE test | MAPE (%) |
| --- | ---: | --- | ---: | ---: |
| `outputs/sarimax/h1/` | 1h | (1,0,2), 4 | 3,016164 | 33,672526 |
| `outputs/sarimax/norefit/` | 24h | (2,0,1), 4 | 3,012486 | 33,252348 |

Cả hai chấm 6.796 giờ. Bảng ứng viên nằm trong `validation_results.csv`, protocol/versions/source hashes trong `metrics.json`, dự báo trong `pred_sarimax.csv`. Phần `lstm_seq24_aligned` trong metadata chỉ là phép cắt lịch sử, không dùng thay `all_test`.

```powershell
# Regenerate metrics/forecast plots from saved CSV, no fit
python main.py sarimax --evaluate-only
# Train canonical 24h; defaults to full train and no refit
python main.py sarimax
# Train canonical 1h
python -m ems.models.sarimax.run_sarimax_h1
```

CLI mặc định ghi `outputs/sarimax/norefit/` và tạo checkpoint dưới `checkpoints/sarimax/`. Wrapper 1h giữ checkpoint trong thư mục tạm, chỉ lưu kết quả. Repo không giữ pickle từ lần refit 2025 cũ. Có thể thử `--refit` với thư mục riêng; kết quả đó không thuộc so sánh chuẩn và không được đưa vào kế hoạch xe yêu cầu no-refit.

`--evaluate-only` dùng `ems.models.sarimax.evaluate`: kiểm tra timestamp/actual khớp toàn bộ test, giá trị hữu hạn không âm, và `lo ≤ pred ≤ hi`; xuất `forecast_evaluation.json` cùng forecast sample và hourly MAE. Không còn tự chạy lịch nhân sự tổng đài, productivity 3 calls/person-hour hoặc chi phí giả USD.

Khoảng dự báo trung tâm 80% có đầu trên danh nghĩa P90; không có nghĩa bảo đảm 80% hoặc 90% mức phục vụ. Phần bố trí xe dùng pipeline chung ở `run_queuing.py`. So sánh theo cùng horizon; không dùng một điểm 1h để kết luận hơn một mô hình 24h.
