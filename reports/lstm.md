# LSTM: rolling 1h và khối 24h

Notebook chính: `notebooks/lstm_experiment.ipynb`. CLI: `python main.py lstm`; thêm `--forecast-horizon 24` cho đầu ra 24h. Thêm `--evaluate-only` để nạp checkpoint/scalers đã lưu, không train hoặc fit lại scalers.

Target `call_count` là số lượt đáp ứng xe MEDIC gom theo `received_dttm`, không phải cuộc gọi duy nhất. Các split dùng chung với Prophet/SARIMAX. Scalers fit trên train; validation dùng chọn epoch, không chọn checkpoint bằng test.

Hai checkpoint Vanilla đang dùng:

| Giao thức | Checkpoint |
| --- | --- |
| Rolling 1h | `checkpoints/lstm/vanilla_1h_rolling_best.pth` |
| Khối 24h | `checkpoints/lstm/vanilla_24h_block_best.pth` |

Cấu hình mặc định: lookback 24, 34 features, hai lớp LSTM hidden 128; xem `ems/models/lstm/config.py` và metadata trong weights để biết cấu hình/epoch thực của artifact. Các kiến trúc mở rộng trong registry vẫn có thể chạy bằng CLI. Weights `vanilla_seq24` cũ đã bỏ; CLI không dùng chúng thay cho thí nghiệm mới.

Rolling 1h lấy cửa sổ features kết thúc tại hàng giờ mục tiêu; các features lịch sử ở hàng này đã được dịch, không phải nhãn tương lai. Test ghép 24 hàng cuối validation làm context nên đủ 6.796 giờ. Khối 24h lấy cửa sổ kết thúc trước giờ mục tiêu, phát hành toàn bộ 24 đầu ra và không đưa actual giữa khối vào dự báo. Các lag trong features của cửa sổ khối có độ trễ riêng; không tuyên bố cả hai nhánh có đầu vào hoàn toàn giống nhau.

Kết quả 24h đã lưu tại `outputs/lstm/metrics_vanilla_24h_block.json` và `test_predictions_vanilla_24h_block.csv`: MAE **3,008991**, RMSE **3,862517**, MAPE **33,968592%**, R² **0,396874**, trên 6.796 giờ. Snapshot web hiện hiển thị LSTM 24h; không có profile LSTM 1h trong snapshot.

Giới hạn cần giữ khi diễn giải: sequence train/validation được tạo độc lập nên mất phần đầu làm lookback. Builder khối pad đuôi ngắn bằng nhãn biên để giữ shape; khi chấm test phải cắt về đúng số giờ có actual bằng `n_target_hours`, không chấm phần pad. Loss train/validation hiện vẫn gồm phần pad ở đuôi; dọn repository không thay đổi quy tắc huấn luyện hoặc kết quả đã công bố. Nếu sửa phương pháp này phải chạy lại thí nghiệm và ghi phiên bản mới.

Generator `scripts/update_lstm_notebook.py` viết lại notebook; chỉ chạy khi chủ động tái tạo, vì nó thay notebook cùng đường dẫn. Notebook đã có output nghiên cứu được giữ trong repo.
