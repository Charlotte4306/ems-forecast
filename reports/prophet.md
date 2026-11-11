# Prophet: dự báo từng giờ

Target là lượt đáp ứng xe MEDIC theo giờ nhận cuộc gọi; cột nguồn vẫn tên `call_count`. Pipeline ở `ems/models/prophet/`, entry point `python main.py prophet`, notebook `notebooks/prophet_experiment.ipynb`.

Fit bốn ứng viên trên train 2019–2024: có/không 14 regressors lịch sử, kết hợp `changepoint_prior_scale=0.01/0.05`. Chọn theo MAE validation 2025, giữ tham số để đánh giá 2026. Kết quả hiện tại chọn `prophet_lags_cp0.05`. Đặc trưng lag/rolling/EWM sử dụng quan sát đến giờ trước; đây là rolling 1h.

| Chỉ số test | Giá trị |
| --- | ---: |
| Số giờ | 6.796 |
| MAE | 3,033880 |
| RMSE | 3,921239 |
| MAPE (%) | 32,925118 |
| R² | 0,378396 |

Nguồn số liệu: `outputs/prophet/metrics.json` → `test_metrics.all_test.prophet`, dự báo tại `outputs/prophet/test_predictions.csv`. Checkpoint `checkpoints/prophet/best_model.json`. Các mục aligned 6.772/6.628 giờ trong metadata là phép cắt so sánh cũ, không phải tập chấm chuẩn hiện tại.

MAE bao gồm actual bằng 0; MAPE bỏ actual bằng 0. Timestamp giữ quy ước CSV, chưa chuẩn hóa DST. Checkpoint tắt uncertainty, không tạo khoảng tin cậy giả. Kết quả 1h không được dùng làm điểm 24h; xem [thí nghiệm 24h](prophet_24h.md). Worker dự báo bảy ngày dùng một Prophet mùa vụ khác, được fit lại hằng ngày.
