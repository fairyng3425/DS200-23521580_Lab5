import argparse
import subprocess
import sys
from pathlib import Path

from config import BASE_DIR, VIDEO_DIR

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def find_videos() -> list[Path]:
    if not VIDEO_DIR.exists():
        return []
    return sorted([p for p in VIDEO_DIR.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS])


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy lần lượt tất cả video trong data/video và lưu output riêng từng video")
    parser.add_argument("--frames", type=int, default=150)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--save-annotated", action="store_true")
    parser.add_argument("--display", action="store_true")
    parser.add_argument("--force-python-report", action="store_true")
    args = parser.parse_args()

    videos = find_videos()
    if not videos:
        print(f"[RunAll] Chưa có video nào trong {VIDEO_DIR}")
        print("[RunAll] Hãy tải video .mp4 và copy vào data/video trước.")
        return

    py = sys.executable
    for idx, video in enumerate(videos, start=1):
        print("\n" + "=" * 80)
        print(f"[RunAll] ({idx}/{len(videos)}) Chạy video: {video.name}")
        print("=" * 80)
        cmd = [
            py,
            "src/run_demo.py",
            "--source",
            str(video.relative_to(BASE_DIR)),
            "--frames",
            str(args.frames),
            "--fps",
            str(args.fps),
        ]
        if args.save_annotated:
            cmd.append("--save-annotated")
        if args.display:
            cmd.append("--display")
        if args.force_python_report:
            cmd.append("--force-python-report")
        returncode = subprocess.call(cmd, cwd=str(BASE_DIR))
        if returncode != 0:
            print(f"[RunAll] Video {video.name} lỗi với return code {returncode}. Tiếp tục video sau.")

    print("\n[RunAll] Đã chạy xong tất cả video.")
    subprocess.call([py, "src/spark_report.py", "--all"], cwd=str(BASE_DIR))


if __name__ == "__main__":
    main()
