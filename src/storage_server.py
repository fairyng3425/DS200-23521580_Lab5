import argparse
import csv
import json
import socket
import time
from collections import defaultdict
from pathlib import Path

from common import ensure_experiment_dirs, iter_json_lines, now_iso, relative_to_base
from config import DEFAULT_STORAGE_HOST, DEFAULT_STORAGE_PORT


class ExperimentStorage:
    def __init__(self, experiment_name: str):
        self.experiment_name = experiment_name
        self.dirs = ensure_experiment_dirs(experiment_name)
        self.jsonl_path = self.dirs["results"] / "detections.jsonl"
        self.csv_path = self.dirs["results"] / "detections.csv"
        self.summary_path = self.dirs["results"] / "summary.json"
        self.rows = []
        self.started_at = time.time()
        self.jsonl_file = self.jsonl_path.open("a", encoding="utf-8")

    def add_detection(self, message: dict) -> None:
        self.rows.append(message)
        self.jsonl_file.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.jsonl_file.flush()

    def finalize(self, end_message: dict | None = None) -> dict:
        self.jsonl_file.flush()
        self.jsonl_file.close()
        self._write_csv()
        summary = self._build_summary(end_message=end_message)
        self.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    def _write_csv(self) -> None:
        fieldnames = [
            "experiment_name",
            "camera_id",
            "source",
            "frame_id",
            "timestamp",
            "processed_at",
            "width",
            "height",
            "person_count",
            "processing_time_ms",
            "annotated_frame",
            "bounding_boxes_json",
        ]
        with self.csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.rows:
                flat = {k: row.get(k, "") for k in fieldnames if k != "bounding_boxes_json"}
                flat["bounding_boxes_json"] = json.dumps(row.get("bounding_boxes", []), ensure_ascii=False)
                writer.writerow(flat)

    def _build_summary(self, end_message: dict | None = None) -> dict:
        counts = [int(r.get("person_count", 0)) for r in self.rows]
        processing_times = [float(r.get("processing_time_ms", 0.0)) for r in self.rows]
        frames = len(self.rows)
        total = sum(counts)
        running_time_seconds = round(time.time() - self.started_at, 2)
        source = self.rows[0].get("source", "") if self.rows else (end_message or {}).get("source", "")
        camera_id = self.rows[0].get("camera_id", "camera_01") if self.rows else (end_message or {}).get("camera_id", "camera_01")
        summary = {
            "generated_at": now_iso(),
            "experiment_name": self.experiment_name,
            "camera_id": camera_id,
            "source": source,
            "frames_processed": frames,
            "total_person_detections": total,
            "avg_persons_per_frame": round(total / frames, 4) if frames else 0,
            "max_persons_in_frame": max(counts) if counts else 0,
            "min_persons_in_frame": min(counts) if counts else 0,
            "avg_processing_time_ms": round(sum(processing_times) / frames, 4) if frames else 0,
            "max_processing_time_ms": round(max(processing_times), 4) if processing_times else 0,
            "min_processing_time_ms": round(min(processing_times), 4) if processing_times else 0,
            "running_time_seconds": running_time_seconds,
            "files": {
                "jsonl": relative_to_base(self.jsonl_path),
                "csv": relative_to_base(self.csv_path),
                "summary": relative_to_base(self.summary_path),
                "annotated_frames_dir": relative_to_base(self.dirs["annotated"]),
            },
        }
        return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Storage Server: nhận và lưu kết quả nhận diện")
    parser.add_argument("--host", default=DEFAULT_STORAGE_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_STORAGE_PORT)
    args = parser.parse_args()

    storages: dict[str, ExperimentStorage] = {}

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((args.host, args.port))
    server_sock.listen(1)
    print(f"[Storage] Đang lắng nghe tại {args.host}:{args.port}")
    print("[Storage] Mỗi video sẽ được lưu riêng trong output\\experiments\\<experiment_name>")
    print("[Storage] Nhấn Ctrl+C để dừng.")

    try:
        conn, addr = server_sock.accept()
        print(f"[Storage] Processing Server đã kết nối từ {addr}")
        with conn:
            for message in iter_json_lines(conn):
                exp = message.get("experiment_name", "experiment")
                if exp not in storages:
                    storages[exp] = ExperimentStorage(exp)
                    print(f"[Storage] Tạo thư mục lưu kết quả cho experiment: {exp}")

                if message.get("type") == "detection":
                    storages[exp].add_detection(message)
                    print(f"[Storage] Lưu frame {message.get('frame_id')} - person_count={message.get('person_count')}")

                elif message.get("type") == "end_stream":
                    summary = storages[exp].finalize(message)
                    print(f"[Storage] Đã nhận end_stream. Summary đã lưu tại {summary['files']['summary']}")
                    print(f"[Storage] Frames={summary['frames_processed']}, Avg persons/frame={summary['avg_persons_per_frame']}")
                    break
    except KeyboardInterrupt:
        print("\n[Storage] Đã dừng bằng Ctrl+C.")
    finally:
        for storage in storages.values():
            try:
                if not storage.jsonl_file.closed:
                    storage.finalize()
            except Exception:
                pass
        server_sock.close()


if __name__ == "__main__":
    main()
