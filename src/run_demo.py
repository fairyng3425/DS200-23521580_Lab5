import argparse
import subprocess
import sys
import time
from pathlib import Path

from common import make_experiment_name
from config import BASE_DIR, DEFAULT_PROCESS_HOST, DEFAULT_PROCESS_PORT, DEFAULT_STORAGE_HOST, DEFAULT_STORAGE_PORT


def start_process(command: list[str], name: str) -> subprocess.Popen:
    print(f"[Demo] Start {name}: {' '.join(command)}")
    return subprocess.Popen(command, cwd=str(BASE_DIR))


def stop_process(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is None:
        print(f"[Demo] Stop {name}")
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy trọn bộ Lab 5: Storage -> Processing -> Frame -> Report")
    parser.add_argument("--source", required=True, help="0 cho webcam hoặc đường dẫn video")
    parser.add_argument("--frames", type=int, default=150)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--camera-id", default="camera_01")
    parser.add_argument("--experiment-name", help="Tên output riêng cho video; nếu bỏ trống sẽ tự sinh theo tên video + thời gian")
    parser.add_argument("--save-annotated", action="store_true")
    parser.add_argument("--display", action="store_true")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--force-python-report", action="store_true", help="Không gọi Spark, tạo report bằng Python fallback")
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args()

    experiment_name = make_experiment_name(args.source, args.experiment_name)
    py = sys.executable

    storage_cmd = [py, "src/storage_server.py", "--host", DEFAULT_STORAGE_HOST, "--port", str(DEFAULT_STORAGE_PORT)]
    processing_cmd = [
        py,
        "src/processing_server.py",
        "--host",
        DEFAULT_PROCESS_HOST,
        "--port",
        str(DEFAULT_PROCESS_PORT),
        "--storage-host",
        DEFAULT_STORAGE_HOST,
        "--storage-port",
        str(DEFAULT_STORAGE_PORT),
        "--conf",
        str(args.conf),
    ]
    if args.save_annotated:
        processing_cmd.append("--save-annotated")

    frame_cmd = [
        py,
        "src/frame_server.py",
        "--source",
        args.source,
        "--processing-host",
        DEFAULT_PROCESS_HOST,
        "--processing-port",
        str(DEFAULT_PROCESS_PORT),
        "--camera-id",
        args.camera_id,
        "--experiment-name",
        experiment_name,
        "--fps",
        str(args.fps),
        "--max-frames",
        str(args.frames),
    ]
    if args.display:
        frame_cmd.append("--display")

    storage_proc = None
    processing_proc = None
    frame_returncode = 1

    try:
        storage_proc = start_process(storage_cmd, "Storage Server")
        time.sleep(1.5)
        processing_proc = start_process(processing_cmd, "Processing Server")
        time.sleep(15.0)
        frame_returncode = subprocess.call(frame_cmd, cwd=str(BASE_DIR))
        time.sleep(2.0)
    finally:
        if processing_proc is not None:
            stop_process(processing_proc, "Processing Server")
        if storage_proc is not None:
            stop_process(storage_proc, "Storage Server")

    if frame_returncode != 0:
        raise SystemExit(f"[Demo] Frame Server kết thúc với mã lỗi {frame_returncode}")

    if not args.no_report:
        report_cmd = [py, "src/spark_report.py", "--experiment-name", experiment_name]
        if args.force_python_report:
            report_cmd.append("--force-python")
        print(f"[Demo] Tạo report cho experiment: {experiment_name}")
        subprocess.call(report_cmd, cwd=str(BASE_DIR))

    print("\n[Demo] Hoàn tất từ đầu đến cuối.")
    print(f"[Demo] Output riêng của video nằm tại: output\\experiments\\{experiment_name}")


if __name__ == "__main__":
    main()
