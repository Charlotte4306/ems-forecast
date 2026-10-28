# EMSForecast: quyết định thiết kế

Người dùng chính là nhà phân tích và người lập kế hoạch EMS. Công việc chính:
đọc nhu cầu theo giờ, nhận biết sai số và khảo sát khả năng đáp ứng. Không có
trang giới thiệu marketing; biểu đồ thời gian là nội dung mở đầu.

## Hệ thống hình thức

- Nền lạnh `#F5F8FA`, bề mặt trắng `#FFFFFF`, chữ `#20384D`.
- Quan sát `#376FAD`: nét liền. Dự báo `#087E8B`: nét đứt.
- Thiếu năng lực `#B55240`: chỉ dùng cho chênh lệch hoặc ngưỡng cần chú ý.
- IBM Plex Sans được lưu cục bộ, gồm glyph tiếng Việt; fallback Segoe UI.
- Thang chữ: 11/12 cho metadata, 13/15 cho dữ liệu, 17 cho tiêu đề phần,
  27/32 cho tên màn hình. Chữ số cân hàng ở số liệu và bảng.
- Nhịp khoảng cách 4/8/12/16/24/32/48px. Căn trái nội dung, căn phải số trong bảng.
- Bo góc 4px cho điều khiển, 6px cho vùng biểu đồ; không dùng gradient hoặc
  bóng dưới từng khối dữ liệu. Đường phân cách mô tả nhóm thông tin.

## Bố cục đã chọn

```text
EMSForecast    Tổng quan | Dự báo nhu cầu | Kế hoạch năng lực
Tên màn hình / phạm vi              Nhãn dữ liệu lịch sử
Bộ lọc ngày, mô hình
Dải tóm tắt (không chia thành các thẻ giống nhau)
Biểu đồ theo giờ                    Giờ đáng chú ý / thông tin mô hình
Bảng đối chiếu hoặc nhịp tuần
Nguồn dữ liệu và phương pháp
```

Capacity Planning đặt giả định cạnh biểu đồ và bảng giờ thiếu năng lực. Giữ các
thanh trượt ở nguyên vị trí khi đổi giả định; kết quả được cập nhật độc lập.

Đã loại cách làm phổ biến trong preview trước: sidebar tối chiếm nhiều diện
tích, một hàng thẻ KPI đồng dạng và hero lớn. Điểm nhấn duy nhất là trục thời
gian: đường quan sát, đường dự báo, mốc phát lại và vùng chưa mở dữ liệu.

## Nội dung phải trung thực

- Tập test lịch sử, không dùng nhãn realtime hoặc dự báo tương lai nhiều ngày.
- ARIMA bị vô hiệu hóa vì chưa có mô hình; không giả kết quả.
- Chưa có phân vùng: chỉ hiển thị toàn thành phố, không tạo bộ lọc khu vực giả.
- Không vẽ dải bất định cho đến khi có kết quả đã được kiểm định.
- WAPE bao gồm sai số tại target bằng 0; chỉ không xác định khi tổng target bằng 0.
- Trong phát lại, dự báo giờ đang xét được mở nhưng actual chưa được mở. CSV và
  metrics mặc định chỉ tính phần đã mở; đánh giá toàn test là lựa chọn riêng rõ nhãn.
- Năng lực xe là mô phỏng có giả định, chưa đủ dữ liệu để tối ưu trạm/ca trực hay nhân lực.

## Tham khảo nghiệp vụ

- Amazon Connect intraday forecast performance: mốc thời gian và actual/forecast.
  https://docs.aws.amazon.com/connect/latest/adminguide/intraday-forecast-performance-dashboard.html
- NICE CXone Intraday: bảng độ lệch cùng interval với biểu đồ.
  https://help.nice-incontact.com/content/workforcemanagement/intraday.htm
- NHS England A&E Forecasting: diễn giải mô hình và độ bất định.
  https://nhsengland.github.io/datascience/our_work/a_and_e_forecasting_tool/

Font: IBM Plex Sans từ Google Fonts; giấy phép OFL tại `assets/FONT-LICENSE.txt`.

## Tự đánh giá trên ứng dụng đang chạy

Đã xem cả ba màn hình ở desktop 1280px và kiểm tra responsive 390px/320px.
Đã sửa tràn ngang do min-width của body, thống nhất kiểu nét của legend với
đường dữ liệu, bổ sung khoảng giờ thiếu năng lực ngay trong Tổng quan và giữ
nguyên vị trí thanh trượt khi tính lại kịch bản. Không dùng animation tự chạy.

Đã kiểm tra đổi mô hình, reset/mở từng giờ, đánh giá toàn test, tải CSV có kèm
giả định, và mở thông tin phương pháp bằng bàn phím. Không có lỗi console ở
các luồng này. Biểu đồ có đường dẫn đọc bằng phím mũi tên và bảng dữ liệu riêng.
CSV ở chế độ phát lại chỉ xuất các giờ đã mở actual; không lộ target của giờ kế tiếp.

Giới hạn: đây là frontend và bộ dữ liệu hậu kiểm đã xuất sẵn, không phải API suy
luận realtime. Chưa kiểm tra bằng thiết bị di động vật lý hoặc triển khai VPS.
