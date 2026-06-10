# DS200 - Lab 5: People Counting System

## 1. Thông tin bài làm

* Môn học: DS200 - Big Data - Lab 5
* Tên: Nguyễn Văn Tiên - MSSV: 23521580
* Chủ đề: Xây dựng hệ thống đếm số người trong video theo hướng xử lý luồng dữ liệu.

## 2. Mục tiêu

Bài làm xây dựng một hệ thống xử lý video theo mô hình nhiều thành phần. Hệ thống đọc từng frame từ video, gửi frame qua socket, nhận diện người bằng mô hình YOLOv8, lưu kết quả phát hiện và tạo báo cáo thống kê cho từng video.

## 3. Kiến trúc hệ thống

Hệ thống gồm ba thành phần chính:

1. `frame_server.py`: đọc video hoặc webcam, trích xuất frame và gửi frame đến Processing Server.
2. `processing_server.py`: nhận frame, dùng YOLOv8 để phát hiện người, vẽ bounding box và gửi kết quả sang Storage Server.
3. `storage_server.py`: nhận kết quả phát hiện, lưu dữ liệu ra file JSONL, CSV, summary và ảnh đã annotate.

Ngoài ra, project có các script hỗ trợ:

* `run_demo.py`: chạy đầy đủ pipeline cho một video.
* `run_all_videos.py`: chạy lần lượt tất cả video trong thư mục `data/video`.
* `spark_report.py`: tạo báo cáo thống kê. Nếu môi trường chưa hỗ trợ Spark/Java phù hợp, chương trình dùng Python fallback để vẫn tạo report đầy đủ.
* `list_results.py`: liệt kê nhanh các kết quả đã chạy.

## 4. Cấu trúc thư mục

```text
DS200-23521580_Lab5/
├── data/
│   └── video/
│       ├── city_square.mp4
│       ├── crowd_city.mp4
│       └── sidewalk.mp4
├── output/
│   ├── experiments/
│   │   ├── city_square_20260611_013521/
│   │   ├── crowd_city_20260611_013614/
│   │   └── sidewalk_20260611_013714/
│   └── all_experiments_summary.csv
├── screen_output/
├── scripts/
├── src/
│   ├── common.py
│   ├── config.py
│   ├── frame_server.py
│   ├── list_results.py
│   ├── processing_server.py
│   ├── run_all_videos.py
│   ├── run_demo.py
│   ├── spark_report.py
│   └── storage_server.py
├── requirements.txt
└── yolov8n.pt
```

## 5. Cài đặt môi trường

Mở PowerShell tại thư mục project và chạy:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Nếu PowerShell không cho kích hoạt môi trường ảo, chạy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\activate
```

## 6. Cách chạy toàn bộ video

Chạy lần lượt tất cả video trong thư mục `data/video`:

```powershell
python src\run_all_videos.py --frames 150 --fps 5 --save-annotated --force-python-report
```

Lệnh này sẽ tự động chạy pipeline cho từng video và lưu kết quả riêng vào:

```text
output/experiments/<ten_video>_<thoi_gian_chay>/
```

## 7. Cách chạy một video riêng

Ví dụ chạy video `city_square.mp4`:

```powershell
python src\run_demo.py --source "data\video\city_square.mp4" --frames 150 --fps 5 --save-annotated --force-python-report
```

Nếu muốn hiển thị video trong lúc chạy, thêm tham số `--display`:

```powershell
python src\run_demo.py --source "data\video\city_square.mp4" --frames 150 --fps 5 --save-annotated --display --force-python-report
```

## 8. Kết quả đầu ra

Mỗi video sau khi chạy sẽ có một thư mục riêng gồm:

```text
annotated_frames/      Ảnh frame đã vẽ bounding box và số người phát hiện
results/
  detections.jsonl     Kết quả phát hiện theo từng frame
  detections.csv       Kết quả dạng bảng
  summary.json         Thống kê tổng hợp của video
report/
  report_summary.json  Báo cáo tổng hợp
  frame_level_report.csv
  frames_by_person_count.csv
```

## 9. Kết quả thực nghiệm

Project đã chạy thử trên 3 video:

| Video           | Số frame | Tổng lượt phát hiện người | Trung bình người/frame | Max | Min |
| --------------- | -------: | ------------------------: | ---------------------: | --: | --: |
| city_square.mp4 |      150 |                      2172 |                  14.48 |  19 |  10 |
| crowd_city.mp4  |      150 |                      1092 |                   7.28 |  12 |   4 |
| sidewalk.mp4    |      150 |                       481 |                 3.2067 |   8 |   0 |

Kết quả chi tiết được lưu trong thư mục `output/experiments` và file `output/all_experiments_summary.csv`.

## 10. Ghi chú

* Video đầu vào được đặt trong thư mục `data/video`.
* Kết quả của mỗi video được lưu tách riêng, không ghi đè lên nhau.
